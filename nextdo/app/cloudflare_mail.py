"""Signed Cloudflare Email Routing receiver, encrypted queue, Groq review tasks."""
from __future__ import annotations
import hashlib,hmac,json,logging,os,re,secrets,sqlite3,threading,time
from datetime import datetime,timezone
from pathlib import Path
from fastapi import HTTPException,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from . import email_intake

LOG=logging.getLogger(__name__)
MAX_BYTES=6_000_000
RETRY_LIMIT=3
INTERVAL=10
PATH="/api/cloudflare-mail/inbound"
RUN_LOCK=threading.Lock()
START_LOCK=threading.Lock()
STARTED=False

def fail(message,code=400):raise HTTPException(status_code=code,detail=message)
def stamp():return datetime.now(timezone.utc).isoformat()
def sec():return int(time.time())
def cfg_path(data):return Path(data)/"cloudflare-mail-local.json"

def load_config(data):
 path=cfg_path(data)
 if not path.exists():return {}
 try:
  d=json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(d,dict):raise ValueError("config")
  if d.get("secret"):
   if not d["secret"].startswith("enc:"):fail("Segreto non cifrato",500)
   d["secret"]=email_intake._cipher(data).decrypt(d["secret"][4:].encode("ascii")).decode()
  return d
 except HTTPException:raise
 except Exception:fail("Configurazione Cloudflare non leggibile",500)

def save_config(data,cfg):
 d=dict(cfg)
 if d.get("secret"):
  d["secret"]="enc:"+email_intake._cipher(data).encrypt(d["secret"].encode()).decode("ascii")
 target=cfg_path(data)
 tmp=target.with_name(target.name+"."+secrets.token_hex(4)+".tmp")
 try:
  fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as out:json.dump(d,out,ensure_ascii=False)
  os.replace(tmp,target)
 finally:tmp.unlink(missing_ok=True)

def public(cfg):
 return {"enabled":bool(cfg.get("enabled")),"secret_configured":bool(cfg.get("secret")),
  "recipient":cfg.get("recipient",""),"allowed_sender":cfg.get("allowed_sender",""),
  "ingest_path":PATH,"interval_seconds":INTERVAL,"requires_gmail":False}

def email_ok(s):return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",s))

def sender_addresses(value):
 return list(dict.fromkeys(address.strip().lower() for address in value.split(",") if address.strip()))

class Config(BaseModel):
 enabled:bool=False
 recipient:str=Field(default="",max_length=254)
 allowed_sender:str=Field(default="",max_length=4096)

def upgrade(db_path):
 with sqlite3.connect(db_path) as db:
  db.execute("PRAGMA foreign_keys=ON")
  db.executescript("""
   CREATE TABLE IF NOT EXISTS cloudflare_mail_inbox(
    message_hash TEXT PRIMARY KEY, source_digest TEXT NOT NULL,
    sender TEXT NOT NULL,recipient TEXT NOT NULL,status TEXT NOT NULL,
    payload_encrypted TEXT,received_at TEXT DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,completed_at TEXT,attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_epoch INTEGER NOT NULL DEFAULT 0,
    tasks_created INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,error TEXT);
   CREATE INDEX IF NOT EXISTS cloudflare_mail_pending
    ON cloudflare_mail_inbox(status,next_attempt_epoch);
   CREATE INDEX IF NOT EXISTS cloudflare_mail_sources
    ON cloudflare_mail_inbox(source_digest);
   CREATE TABLE IF NOT EXISTS cloudflare_mail_tasks(
    fingerprint TEXT PRIMARY KEY,
    message_hash TEXT NOT NULL REFERENCES cloudflare_mail_inbox(message_hash),
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  """)

def verify(headers,raw,cfg):
 if not cfg.get("enabled") or not cfg.get("secret"):fail("Ricezione Cloudflare disattivata",503)
 ts=headers.get("x-nextdo-timestamp","")
 sig=headers.get("x-nextdo-signature","")
 sender=headers.get("x-nextdo-envelope-from","").strip().lower()
 recipient=headers.get("x-nextdo-envelope-to","").strip().lower()
 if not re.fullmatch(r"[0-9]{10,13}",ts):fail("Timestamp non valido",401)
 t=int(ts)//(1000 if len(ts)==13 else 1)
 if abs(sec()-t)>300:fail("Messaggio scaduto",401)
 if not re.fullmatch(r"[0-9a-f]{64}",sig):fail("Firma mancante o non valida",401)
 if not email_ok(sender) or not email_ok(recipient):fail("Indirizzi non validi",401)
 payload=(ts+"\n"+sender+"\n"+recipient+"\n").encode()+raw
 expected=hmac.new(cfg["secret"].encode(),payload,hashlib.sha256).hexdigest()
 if not hmac.compare_digest(expected,sig):fail("Firma Cloudflare non valida",401)
 if recipient!=cfg.get("recipient","").lower():fail("Destinatario inatteso",403)
 if sender not in sender_addresses(cfg.get("allowed_sender","")):fail("Mittente non autorizzato",403)
 return sender,recipient

def digest(source):
 title=re.sub(r"\s+"," ",source["subject"]).strip().casefold()
 body=re.sub(r"\s+"," ",source["text"]).strip().casefold()
 return hashlib.sha256((title+"\n"+body).encode()).hexdigest()

def enqueue(conn,data,raw,sender,recipient):
 source=email_intake.parse_mail(raw)
 sha=hashlib.sha256(raw).hexdigest()
 fingerprint=digest(source)
 with conn() as c:
  row=c.execute("SELECT status FROM cloudflare_mail_inbox WHERE message_hash=?",(sha,)).fetchone()
  if row:return {"accepted":True,"duplicate":True,"state":row["status"]}
  existing=c.execute("SELECT 1 FROM cloudflare_mail_inbox WHERE source_digest=? AND status IN ('processed','duplicate') LIMIT 1",(fingerprint,)).fetchone()
  if existing:
   c.execute("INSERT INTO cloudflare_mail_inbox(message_hash,source_digest,sender,recipient,status,completed_at) VALUES(?,?,?,?,'duplicate',?)",
    (sha,fingerprint,sender,recipient,stamp()))
   return {"accepted":True,"duplicate":True,"state":"duplicate"}
  encrypted=email_intake._cipher(data).encrypt(json.dumps(source,ensure_ascii=False).encode()).decode()
  c.execute("INSERT INTO cloudflare_mail_inbox(message_hash,source_digest,sender,recipient,status,payload_encrypted) VALUES(?,?,?,?,'queued',?)",
   (sha,fingerprint,sender,recipient,encrypted))
 return {"accepted":True,"duplicate":False,"state":"queued"}

def _claim(conn):
 with conn() as c:
  r=c.execute("SELECT message_hash,source_digest,payload_encrypted,sender,recipient,attempt_count FROM cloudflare_mail_inbox WHERE status IN ('queued','retry') AND attempt_count<? AND next_attempt_epoch<=? ORDER BY received_at,message_hash LIMIT 1",(RETRY_LIMIT,sec())).fetchone()
  if r:c.execute("UPDATE cloudflare_mail_inbox SET status='processing',attempt_count=attempt_count+1,started_at=?,error=NULL WHERE message_hash=?",(stamp(),r["message_hash"]))
  return dict(r) if r else None

def process_one(conn,data,row):
 sha=row["message_hash"]
 try:
  with conn() as c:
   previous=c.execute("SELECT 1 FROM cloudflare_mail_inbox WHERE source_digest=? AND message_hash<>? AND status IN ('processed','duplicate') LIMIT 1",(row["source_digest"],sha)).fetchone()
   if previous:
    c.execute("UPDATE cloudflare_mail_inbox SET status='duplicate',payload_encrypted=NULL,completed_at=? WHERE message_hash=?",(stamp(),sha))
    return {"created":0,"duplicate":True}
  raw=email_intake._cipher(data).decrypt(row["payload_encrypted"].encode())
  source=json.loads(raw.decode("utf-8"))
  proposals=email_intake.analyze(email_intake.load_config(data),source)["proposals"]
  cfg=load_config(data)
  owner=cfg.get("owner_id")
  created=duplicate_count=0
  with conn() as c:
   if not c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(owner,)).fetchone():
    raise ValueError("Owner inactive")
   for item in proposals:
    title=item["title"][:250];evidence=item["evidence"][:600]
    due=item.get("due_date") or None
    fp=hashlib.sha256((title.casefold()+"\n"+(due or "")+"\n"+evidence.casefold()).encode()).hexdigest()
    if c.execute("SELECT 1 FROM cloudflare_mail_tasks WHERE fingerprint=?",(fp,)).fetchone():
     duplicate_count+=1;continue
    description=("[DA VERIFICARE] Scadenza generata automaticamente, non convalidata.\n"
     "Origine: Cloudflare Email Routing\nMessaggio: "+sha+"\nImpronta testo: "+row["source_digest"]+
     "\nMittente SMTP: "+row["sender"]+"\nDestinatario SMTP: "+row["recipient"]+
     "\nMittente intestazione: "+source["sender"]+"\nOggetto: "+source["subject"]+
     "\nData email: "+source["date"]+"\nFrase originale: "+evidence+
     "\nOra, CdS e incaricati: [DA VERIFICARE].")
    cur=c.execute(
     "INSERT INTO tasks(title,description,kind,priority,status,due_at,start_at,owner_id,"
     "assigned_to,group_id,completion_mode,display_enabled,recurrence,labels,scope,project_id)"
     " VALUES(?,?,'task','normal','review',?,NULL,?,NULL,NULL,'global',0,'none',?,'personal',NULL)",
     (title,description,due,owner,json.dumps(["Cloudflare Mail","Da verificare"],ensure_ascii=False)))
    tid=cur.lastrowid
    c.execute("INSERT INTO cloudflare_mail_tasks(fingerprint,message_hash,task_id) VALUES(?,?,?)",(fp,sha,tid))
    c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",
     (owner,"cloudflare_mail_create_unverified","task",tid))
    created+=1
   c.execute("UPDATE cloudflare_mail_inbox SET status='processed',payload_encrypted=NULL,completed_at=?,tasks_created=?,duplicates=? WHERE message_hash=?",
    (stamp(),created,duplicate_count,sha))
  return {"created":created}
 except Exception as exc:
  attempts=row["attempt_count"]+1
  final=attempts>=RETRY_LIMIT
  reason="Errore elaborazione messaggio"
  if isinstance(exc,HTTPException):reason="Errore GroqCloud HTTP "+str(exc.status_code)
  with conn() as c:
   c.execute("UPDATE cloudflare_mail_inbox SET status=?,error=?,next_attempt_epoch=?,completed_at=? WHERE message_hash=?",
    ("failed" if final else "retry",reason,sec()+300*attempts,stamp() if final else None,sha))
  LOG.warning("Cloudflare email processing failed (attempt %d)",attempts)
  return {"created":0,"error":True}

def run_queue(conn,data):
 if not RUN_LOCK.acquire(blocking=False):return {"busy":True,"processed":0,"created":0,"errors":0}
 try:
  result={"busy":False,"processed":0,"created":0,"errors":0}
  for _ in range(5):
   row=_claim(conn)
   if not row:break
   outcome=process_one(conn,data,row)
   result["processed"]+=1;result["created"]+=outcome["created"]
   if outcome.get("error"):result["errors"]+=1
  return result
 finally:RUN_LOCK.release()

def worker_loop(conn,data):
 while True:
  time.sleep(INTERVAL)
  try:
   cfg=load_config(data)
   if not cfg.get("enabled"):continue
   # Requeue stale processing claims after interrupted launches.
   with conn() as c:
    c.execute("UPDATE cloudflare_mail_inbox SET status=CASE WHEN attempt_count>=? THEN 'failed' ELSE 'retry' END,next_attempt_epoch=?,completed_at=CASE WHEN attempt_count>=? THEN ? ELSE NULL END WHERE status='processing' AND started_at<?",
     (RETRY_LIMIT,sec(),RETRY_LIMIT,stamp(),datetime.fromtimestamp(time.time()-180,timezone.utc).isoformat()))
    c.execute("UPDATE cloudflare_mail_inbox SET payload_encrypted=NULL WHERE status='failed' AND received_at<datetime('now','-7 days')")
   run_queue(conn,data)
  except Exception:LOG.warning("NextDo Cloudflare email queue retry deferred")

def register_routes(app,*,conn,user,csrf,data_path):
 def admin(req):
  u=user(req)
  if u["role"]!="admin":fail("Solo l'amministratore può gestire le email",403)
  return u
 @app.on_event("startup")
 def start_worker():
  global STARTED
  with START_LOCK:
   if not STARTED:
    STARTED=True
    threading.Thread(target=worker_loop,args=(conn,data_path),daemon=True,
      name="nextdo-cloudflare-mail").start()
 @app.get("/api/cloudflare-mail/config")
 def get_config(req:Request):
  admin(req);return public(load_config(data_path))
 @app.post("/api/cloudflare-mail/config")
 def set_config(body:Config,req:Request):
  owner=admin(req);csrf(req)
  cfg=load_config(data_path)
  recipient=body.recipient.strip().lower()
  senders=sender_addresses(body.allowed_sender)
  if recipient and not email_ok(recipient):fail("Destinatario non valido")
  if any(len(sender)>254 or not email_ok(sender) for sender in senders):fail("Mittente non valido")
  if body.enabled and (not cfg.get("secret") or not recipient or not senders):
   fail("Configurare gli indirizzi e generare il segreto prima di attivare la ricezione")
  cfg.update(enabled=body.enabled,recipient=recipient,allowed_sender=", ".join(senders),owner_id=owner["id"])
  save_config(data_path,cfg)
  return public(cfg)
 @app.post("/api/cloudflare-mail/secret")
 def new_secret(req:Request):
  owner=admin(req);csrf(req)
  cfg=load_config(data_path)
  cfg.update(secret=secrets.token_urlsafe(48),owner_id=owner["id"],enabled=False)
  save_config(data_path,cfg)
  return {"secret":cfg["secret"],"warning":"Copia il segreto nel Worker Cloudflare: viene mostrato una sola volta."}
 @app.post(PATH)
 async def inbound(req:Request):
  if req.headers.get("content-type","").split(";")[0].strip().lower()!="message/rfc822":
   fail("Formato non valido",415)
  try:size=int(req.headers.get("content-length") or 0)
  except ValueError:fail("Dimensione non valida",400)
  if size>MAX_BYTES:fail("Messaggio troppo grande",413)
  raw=await req.body()
  if not raw or len(raw)>MAX_BYTES:fail("Messaggio vuoto o troppo grande",413)
  sender,recipient=verify(req.headers,raw,load_config(data_path))
  return JSONResponse(enqueue(conn,data_path,raw,sender,recipient),status_code=202)
 @app.post("/api/cloudflare-mail/process")
 def process(req:Request):
  admin(req);csrf(req);return run_queue(conn,data_path)
 @app.post("/api/cloudflare-mail/retry-failed")
 def retry_failed(req:Request):
  admin(req);csrf(req)
  with conn() as c:
   result=c.execute("UPDATE cloudflare_mail_inbox SET status='retry',attempt_count=0,next_attempt_epoch=0,error=NULL,completed_at=NULL WHERE status='failed' AND payload_encrypted IS NOT NULL")
   return {"queued":result.rowcount}
 @app.get("/api/cloudflare-mail/history")
 def history(req:Request):
  admin(req)
  with conn() as c:
   return [dict(r) for r in c.execute(
    "SELECT message_hash,sender,recipient,status,attempt_count,tasks_created,duplicates,received_at,completed_at,error FROM cloudflare_mail_inbox ORDER BY received_at DESC LIMIT 40")]
