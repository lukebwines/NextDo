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
RETENTION_DAYS=30
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
  "private_sender":cfg.get("private_sender",""),
  "ingest_path":PATH,"interval_seconds":INTERVAL,"requires_gmail":False,"retention_days":RETENTION_DAYS}

def email_ok(s):return bool(re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}",s))

def sender_addresses(value):
 return list(dict.fromkeys(address.strip().lower() for address in value.split(",") if address.strip()))

class Config(BaseModel):
 enabled:bool=False
 recipient:str=Field(default="",max_length=254)
 allowed_sender:str=Field(default="",max_length=4096)
 private_sender:str|None=Field(default=None,max_length=4096)

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
  cols={r[1] for r in db.execute("PRAGMA table_info(cloudflare_mail_inbox)")}
  if "area" not in cols:db.execute("ALTER TABLE cloudflare_mail_inbox ADD COLUMN area TEXT NOT NULL DEFAULT 'work'")
  if "private_owner" not in cols:db.execute("ALTER TABLE cloudflare_mail_inbox ADD COLUMN private_owner INTEGER")
  if "private_identity" not in cols:db.execute("ALTER TABLE cloudflare_mail_inbox ADD COLUMN private_identity TEXT")
  # Separate ledger: never point private items at professional task IDs.
  db.execute("""CREATE TABLE IF NOT EXISTS cloudflare_private_fingerprints(
   fingerprint TEXT PRIMARY KEY,message_hash TEXT NOT NULL REFERENCES cloudflare_mail_inbox(message_hash),
   private_item_id INTEGER REFERENCES private_items(id) ON DELETE SET NULL)""")

def private_insert(c,owner,row,source,item,fp,title,description,kind,due):
 from . import private_items
 if not c.execute("SELECT 1 FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE u.id=? AND p.owner=? AND u.active=1 AND u.role='admin'",(owner,row.get("private_identity"))).fetchone():raise ValueError("Private destination inactive")
 if c.execute("SELECT 1 FROM cloudflare_private_fingerprints WHERE fingerprint=?",(fp,)).fetchone():return False
 if kind!="appointment":kind="deadline" if due else "task"
 tid=private_items.create(c,owner,{"title":title,"description":description,"kind":kind,"due_at":due,"status":"review"})
 c.execute("INSERT INTO cloudflare_private_fingerprints VALUES(?,?,?)",(fp,row["message_hash"],tid))
 return True

def purge_expired(c):
 # Delete message text, never the operational tasks or deduplication ledger.
 c.execute("""UPDATE cloudflare_mail_inbox SET payload_encrypted=NULL,
  status=CASE WHEN status IN ('queued','retry') THEN 'failed' ELSE status END,
  error=CASE WHEN status IN ('queued','retry') THEN 'Testo scaduto: inoltrare nuovamente' ELSE error END
  WHERE payload_encrypted IS NOT NULL AND received_at<=datetime('now','-30 days') AND status!='processing'""")

def decode_source(data,row):
 if not row["payload_encrypted"]:fail("Testo non disponibile: reinoltrare l'email",410)
 try:return json.loads(email_intake._cipher(data).decrypt(row["payload_encrypted"].encode()).decode("utf-8"))
 except Exception:fail("Testo cifrato non leggibile",409)

def represented(c,source_digest,exclude=None):
 # A previous empty successful analysis must not suppress a new forwarding.
 return c.execute("""SELECT 1 FROM cloudflare_mail_inbox WHERE source_digest=? AND message_hash!=?
  AND (tasks_created>0 OR duplicates>0 OR EXISTS(SELECT 1 FROM cloudflare_mail_tasks l WHERE l.message_hash=cloudflare_mail_inbox.message_hash))
  LIMIT 1""",(source_digest,exclude or "")).fetchone()

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

def enqueue(conn,data,raw,sender,recipient,cfg=None):
 source=email_intake.parse_mail(raw)
 cfg=cfg if cfg is not None else load_config(data)
 private=sender in sender_addresses(cfg.get("private_sender",""))
 owner=cfg.get("private_owner_id") if private else None
 identity=cfg.get("private_identity") if private else None
 if private and (not isinstance(owner,int) or not isinstance(identity,str) or not identity):fail("Destinazione personale non configurata",503)
 area="private" if private else "work"
 prefix=("private:"+identity+":").encode() if private else b""
 sha=hashlib.sha256(prefix+raw).hexdigest()
 fingerprint=hashlib.sha256(prefix+digest(source).encode()).hexdigest() if private else digest(source)
 with conn() as c:
  purge_expired(c)
  if private and not c.execute("SELECT 1 FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE u.id=? AND p.owner=? AND u.active=1 AND u.role='admin'",(owner,identity)).fetchone():fail("Destinazione personale non disponibile",503)
  row=c.execute("SELECT * FROM cloudflare_mail_inbox WHERE message_hash=?",(sha,)).fetchone()
  if row:
   if row["status"] in ("processed","failed") and row["tasks_created"]==0 and row["duplicates"]==0 and not row["payload_encrypted"] and not represented(c,fingerprint,sha):
    encrypted=email_intake._cipher(data).encrypt(json.dumps(source,ensure_ascii=False).encode()).decode()
    c.execute("""UPDATE cloudflare_mail_inbox SET status='queued',payload_encrypted=?,received_at=CURRENT_TIMESTAMP,
      attempt_count=0,next_attempt_epoch=0,started_at=NULL,completed_at=NULL,error=NULL WHERE message_hash=?""",(encrypted,sha))
    return {"accepted":True,"duplicate":False,"state":"queued"}
   return {"accepted":True,"duplicate":True,"state":row["status"]}
  encrypted=email_intake._cipher(data).encrypt(json.dumps(source,ensure_ascii=False).encode()).decode()
  if represented(c,fingerprint):
   c.execute("INSERT INTO cloudflare_mail_inbox(message_hash,source_digest,sender,recipient,status,completed_at,payload_encrypted,area,private_owner,private_identity) VALUES(?,?,?,?,'duplicate',?,?,?,?,?)",
    (sha,fingerprint,sender,recipient,stamp(),encrypted,area,owner,identity))
   return {"accepted":True,"duplicate":True,"state":"duplicate"}
  c.execute("INSERT INTO cloudflare_mail_inbox(message_hash,source_digest,sender,recipient,status,payload_encrypted,area,private_owner,private_identity) VALUES(?,?,?,?,'queued',?,?,?,?)",
   (sha,fingerprint,sender,recipient,encrypted,area,owner,identity))
 return {"accepted":True,"duplicate":False,"state":"queued"}

def _claim(conn):
 with conn() as c:
  purge_expired(c)
  r=c.execute("SELECT message_hash,source_digest,payload_encrypted,sender,recipient,attempt_count,area,private_owner,private_identity FROM cloudflare_mail_inbox WHERE status IN ('queued','retry') AND payload_encrypted IS NOT NULL AND attempt_count<? AND next_attempt_epoch<=? ORDER BY received_at,message_hash LIMIT 1",(RETRY_LIMIT,sec())).fetchone()
  if r:c.execute("UPDATE cloudflare_mail_inbox SET status='processing',attempt_count=attempt_count+1,started_at=?,error=NULL WHERE message_hash=?",(stamp(),r["message_hash"]))
  return dict(r) if r else None

def process_one(conn,data,row):
 sha=row["message_hash"]
 try:
  with conn() as c:
   previous=represented(c,row["source_digest"],sha)
   if previous:
    c.execute("UPDATE cloudflare_mail_inbox SET status='duplicate',completed_at=? WHERE message_hash=?",(stamp(),sha))
    return {"created":0,"duplicate":True}
  raw=email_intake._cipher(data).decrypt(row["payload_encrypted"].encode())
  source=json.loads(raw.decode("utf-8"))
  proposals=email_intake.analyze(email_intake.load_config(data),source)["proposals"]
  if not proposals:proposals=[email_intake.manual_proposal(source)]
  cfg=load_config(data)
  private=row.get("area")=="private"
  owner=row.get("private_owner") if private else cfg.get("owner_id")
  created=duplicate_count=0
  auto_items=[]
  with conn() as c:
   if not c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(owner,)).fetchone():
    raise ValueError("Owner inactive")
   for item in proposals:
    title=item["title"][:250];evidence=item["evidence"][:600]
    kind="appointment" if item.get("kind")=="appointment" else "task"
    due=item.get("due_date") or None
    if kind=="appointment" and due and item.get("appointment_time"):
     due+="T"+item["appointment_time"]+":00"
    fp=hashlib.sha256((title.casefold()+"\n"+(due or "")+"\n"+evidence.casefold()).encode()).hexdigest()
    if item.get("manual_review"):fp=hashlib.sha256(("manual-review:"+row["source_digest"]).encode()).hexdigest()
    if private:fp=hashlib.sha256(("private:"+str(row.get("private_identity"))+":"+fp).encode()).hexdigest()
    if not private and c.execute("SELECT 1 FROM cloudflare_mail_tasks WHERE fingerprint=?",(fp,)).fetchone():
     duplicate_count+=1;continue
    description=("[DA VERIFICARE] Scadenza generata automaticamente, non convalidata.\n"
     "Origine: Cloudflare Email Routing\nMessaggio: "+sha+"\nImpronta testo: "+row["source_digest"]+
     "\nMittente SMTP: "+row["sender"]+"\nDestinatario SMTP: "+row["recipient"]+
     "\nMittente intestazione: "+source["sender"]+"\nOggetto: "+source["subject"]+
     "\nData email: "+source["date"]+"\nFrase originale: "+evidence+
     "\nOra, CdS e incaricati: [DA VERIFICARE].")
    description+="\n"+item.get("description","")
    if item.get("manual_review"):description+="\nNessuna data assegnata." + ("\nTesto email:\n"+source["text"][:12000] if private else " Aprire il registro email per esaminare il testo disponibile.")
    if private:
     if private_insert(c,owner,row,source,item,fp,title,description,kind,due):created+=1
     else:duplicate_count+=1
     continue
    cur=c.execute(
     "INSERT INTO tasks(title,description,kind,priority,status,due_at,start_at,owner_id,"
     "assigned_to,group_id,completion_mode,display_enabled,recurrence,labels,scope,project_id)"
     " VALUES(?,?,?,'normal','review',?,NULL,?,NULL,NULL,'global',0,'none',?,'personal',NULL)",
     (title,description,kind,due,owner,json.dumps(["Cloudflare Mail","Da verificare"],ensure_ascii=False)))
    tid=cur.lastrowid
    c.execute("INSERT INTO cloudflare_mail_tasks(fingerprint,message_hash,task_id) VALUES(?,?,?)",(fp,sha,tid))
    c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",
     (owner,"cloudflare_mail_create_unverified","task",tid))
    created+=1;auto_items.append((tid,item))
   c.execute("UPDATE cloudflare_mail_inbox SET status='processed',completed_at=?,tasks_created=?,duplicates=? WHERE message_hash=?",
    (stamp(),created,duplicate_count,sha))
   # Outbox creation is atomic with tasks; an optional feature failure never rolls back intake.
   if private:return {"created":created}
   c.execute("SAVEPOINT automatic_ics")
   try:
    from . import automatic_ics
    automatic_ics.enqueue(c,data,row,source,owner,auto_items)
    c.execute("RELEASE automatic_ics")
   except Exception:
    c.execute("ROLLBACK TO automatic_ics");c.execute("RELEASE automatic_ics")
    LOG.warning("Automatic ICS enqueue failed")
  return {"created":created}
 except Exception as exc:
  attempts=row["attempt_count"]+1
  final=attempts>=RETRY_LIMIT
  reason="Errore elaborazione messaggio"
  fallback_created=0
  if isinstance(exc,HTTPException):reason="Errore GroqCloud HTTP "+str(exc.status_code)
  with conn() as c:
   if final and isinstance(exc,HTTPException):
    try:
     private=row.get("area")=="private"
     owner=row.get("private_owner") if private else load_config(data).get("owner_id")
     source=decode_source(data,row)
     if c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(owner,)).fetchone():
      fp=hashlib.sha256(("manual-review:"+row["source_digest"]).encode()).hexdigest()
      if private:
       fp=hashlib.sha256(("private:"+str(row.get("private_identity"))+":"+fp).encode()).hexdigest()
       proposal=email_intake.manual_proposal(source,"Analisi AI non riuscita dopo tre tentativi.")
       desc="[DA VERIFICARE] Analisi AI non riuscita.\n"+source["subject"]+"\n"+source["text"][:12000]
       if private_insert(c,owner,row,source,proposal,fp,proposal["title"],desc,"task",None):
        c.execute("UPDATE cloudflare_mail_inbox SET tasks_created=tasks_created+1 WHERE message_hash=?",(sha,));fallback_created=1
      elif not c.execute("SELECT 1 FROM cloudflare_mail_tasks WHERE fingerprint=?",(fp,)).fetchone():
       proposal=email_intake.manual_proposal(source,"Analisi AI non riuscita dopo tre tentativi.")
       desc="[DA VERIFICARE] Analisi AI non riuscita. Origine: Cloudflare Email Routing\nMessaggio: "+sha+"\nOggetto: "+source["subject"]+"\nConsultare il registro email per il testo. Nessuna data assegnata."
       cur=c.execute("""INSERT INTO tasks(title,description,kind,priority,status,owner_id,scope,labels)
         VALUES(?,?,'task','normal','review',?,'personal',?)""",(proposal["title"],desc,owner,json.dumps(["Cloudflare Mail","Da verificare"])))
       c.execute("INSERT INTO cloudflare_mail_tasks(fingerprint,message_hash,task_id) VALUES(?,?,?)",(fp,sha,cur.lastrowid))
       c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",(owner,"cloudflare_mail_create_unverified","task",cur.lastrowid))
       c.execute("UPDATE cloudflare_mail_inbox SET tasks_created=tasks_created+1 WHERE message_hash=?",(sha,))
       fallback_created=1
    except (HTTPException,ValueError,KeyError):pass
   c.execute("UPDATE cloudflare_mail_inbox SET status=?,error=?,next_attempt_epoch=?,completed_at=? WHERE message_hash=?",
    ("failed" if final else "retry",reason,sec()+300*attempts,stamp() if final else None,sha))
  LOG.warning("Cloudflare email processing failed (attempt %d)",attempts)
  return {"created":fallback_created,"error":True}

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
   # Purge retained text even when automatic intake is disabled or config is unreadable.
   # Requeue stale processing claims after interrupted launches.
   with conn() as c:
    c.execute("UPDATE cloudflare_mail_inbox SET status=CASE WHEN attempt_count>=? THEN 'failed' ELSE 'retry' END,next_attempt_epoch=?,completed_at=CASE WHEN attempt_count>=? THEN ? ELSE NULL END WHERE status='processing' AND started_at<?",
     (RETRY_LIMIT,sec(),RETRY_LIMIT,stamp(),datetime.fromtimestamp(time.time()-180,timezone.utc).isoformat()))
    purge_expired(c)
   if load_config(data).get("enabled"):run_queue(conn,data)
   from . import automatic_ics
   automatic_ics.run_one(conn,data)
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
  if cfg.get("private_identity") and cfg.get("private_owner_id")!=owner["id"]:fail("La configurazione personale appartiene a un altro account",403)
  private_senders=sender_addresses(body.private_sender if body.private_sender is not None else cfg.get("private_sender",""))
  if any(x not in senders for x in private_senders):fail("I mittenti personali devono essere tra quelli autorizzati")
  if private_senders:
   if cfg.get("private_identity") and cfg.get("private_owner_id")!=owner["id"]:fail("La destinazione personale appartiene a un altro account",403)
   with conn() as c:
    c.execute("INSERT OR IGNORE INTO personal_identities(user_id,owner) VALUES(?,?)",(owner["id"],secrets.token_hex(32)))
    identity=c.execute("SELECT owner FROM personal_identities WHERE user_id=?",(owner["id"],)).fetchone()[0]
   cfg.update(private_owner_id=owner["id"],private_identity=identity)
  else:
   cfg.pop("private_owner_id",None);cfg.pop("private_identity",None)
  cfg.update(enabled=body.enabled,recipient=recipient,allowed_sender=", ".join(senders),private_sender=", ".join(private_senders),owner_id=owner["id"])
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
  cfg=load_config(data_path)
  sender,recipient=verify(req.headers,raw,cfg)
  return JSONResponse(enqueue(conn,data_path,raw,sender,recipient,cfg),status_code=202)
 @app.post("/api/cloudflare-mail/process")
 def process(req:Request):
  admin(req);csrf(req);return run_queue(conn,data_path)
 @app.post("/api/cloudflare-mail/retry-failed")
 def retry_failed(req:Request):
  admin(req);csrf(req)
  with conn() as c:
   purge_expired(c)
   result=c.execute("UPDATE cloudflare_mail_inbox SET status='retry',attempt_count=0,next_attempt_epoch=0,error=NULL,completed_at=NULL WHERE status='failed' AND payload_encrypted IS NOT NULL AND tasks_created=0 AND duplicates=0")
   return {"queued":result.rowcount}
 def get_entry(c,sha):
  if not re.fullmatch(r"[a-f0-9]{64}",sha):fail("Messaggio non valido",404)
  purge_expired(c)
  row=c.execute("SELECT * FROM cloudflare_mail_inbox WHERE message_hash=?",(sha,)).fetchone()
  if not row or row["area"]!="work":fail("Messaggio non trovato",404)
  return row
 def links(c,row):
  return [dict(t) for t in c.execute("""SELECT l.task_id,t.title,t.status FROM cloudflare_mail_tasks l
   JOIN cloudflare_mail_inbox i ON i.message_hash=l.message_hash
   LEFT JOIN tasks t ON t.id=l.task_id WHERE i.source_digest=? ORDER BY l.created_at""",(row["source_digest"],))]
 @app.get("/api/cloudflare-mail/history")
 def history(req:Request):
  admin(req)
  with conn() as c:
   purge_expired(c)
   rows=c.execute("""SELECT message_hash,source_digest,sender,recipient,status,attempt_count,tasks_created,duplicates,
     received_at,completed_at,error,payload_encrypted,datetime(received_at,'+30 days') AS retained_until
     FROM cloudflare_mail_inbox WHERE area='work' ORDER BY received_at DESC LIMIT 40""").fetchall()
   output=[]
   for row in rows:
    item={k:row[k] for k in row.keys() if k!="payload_encrypted"}
    item["subject"]=None;item["text_available"]=False
    if row["payload_encrypted"]:
     try:item["subject"]=decode_source(data_path,row)["subject"];item["text_available"]=True
     except HTTPException:pass
    item["linked_tasks"]=links(c,row)
    output.append(item)
   return JSONResponse(output,headers={"Cache-Control":"no-store"})
 @app.get("/api/cloudflare-mail/history/{sha}")
 def original(sha:str,req:Request):
  admin(req)
  with conn() as c:
   row=get_entry(c,sha);source=decode_source(data_path,row)
   return JSONResponse({"source":source,"linked_tasks":links(c,row),"status":row["status"],
     "retained_until":c.execute("SELECT datetime(?,'+30 days')",(row["received_at"],)).fetchone()[0]},headers={"Cache-Control":"no-store"})
 @app.post("/api/cloudflare-mail/history/{sha}/reanalyze")
 def reanalyze(sha:str,req:Request):
  admin(req);csrf(req)
  with conn() as c:
   row=get_entry(c,sha)
   if row["status"] in ("queued","retry","processing"):fail("Attendere la fine dell'elaborazione",409)
   source=decode_source(data_path,row);associated=links(c,row)
  result=email_intake.analyze(email_intake.load_config(data_path),source)
  if not result["proposals"]:result["proposals"]=[email_intake.manual_proposal(source)]
  result["linked_tasks"]=associated
  # Preview only: never overwrite or duplicate already generated activities.
  return JSONResponse(result,headers={"Cache-Control":"no-store"})
 @app.post("/api/cloudflare-mail/history/{sha}/requeue")
 def requeue(sha:str,req:Request):
  admin(req);csrf(req)
  with conn() as c:
   row=get_entry(c,sha);decode_source(data_path,row)
   if row["status"] not in ("processed","failed") or row["tasks_created"] or row["duplicates"] or represented(c,row["source_digest"]):
    fail("Attività già generate o messaggio in elaborazione: usare la rianalisi in anteprima",409)
   c.execute("""UPDATE cloudflare_mail_inbox SET status='queued',attempt_count=0,next_attempt_epoch=0,error=NULL,completed_at=NULL
     WHERE message_hash=?""",(sha,))
   return {"queued":True}
 @app.delete("/api/cloudflare-mail/history/{sha}/text")
 def delete_text(sha:str,req:Request):
  admin(req);csrf(req)
  with conn() as c:
   row=get_entry(c,sha)
   if row["status"] in ("queued","retry","processing"):fail("Attendere la fine dell'elaborazione",409)
   c.execute("UPDATE cloudflare_mail_inbox SET payload_encrypted=NULL WHERE message_hash=?",(sha,))
  return {"ok":True}
