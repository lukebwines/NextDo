"""Opt-in automatic tentative ICS replies to a fixed, verified recipient."""
from datetime import datetime,date,timedelta,timezone
from zoneinfo import ZoneInfo
import hashlib,json,logging,re,secrets,time,os
from fastapi import Request
from pydantic import BaseModel,Field
from . import outbound_mail as mail,calendar_export as ical,email_intake

LOG=logging.getLogger(__name__)
MARKER="NextDo - ICS automatico da verificare"
TZ=ZoneInfo(os.environ.get("NEXTDO_TZ","Europe/Rome"))
def table(c):
 c.execute("""CREATE TABLE IF NOT EXISTS automatic_ics_queue(
  source_digest TEXT PRIMARY KEY,message_hash TEXT NOT NULL,rule_id TEXT NOT NULL,
  owner_id INTEGER NOT NULL,recipient TEXT NOT NULL,items TEXT NOT NULL,created_epoch INTEGER NOT NULL,
  status TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '')""")

def rule(cfg):
 a=cfg.get("automatic_ics") or {}
 return a if isinstance(a,dict) else {}
def valid_rule(cfg):
 a=rule(cfg)
 return bool(cfg.get("enabled") and cfg.get("tested") and cfg.get("token") and a.get("enabled")
  and a.get("id") and a.get("recipient") in cfg.get("recipients",[]) and a.get("owner_id"))
def public(cfg):
 a=rule(cfg)
 return {"enabled":valid_rule(cfg),"recipient":a.get("recipient",""),"ready":bool(cfg.get("enabled") and cfg.get("tested")),
  "recipients":cfg.get("recipients",[])}

def eligible(item,source,tz):
 if item.get("manual_review"):return False
 due=item.get("due_date") or ""
 try:d=date.fromisoformat(due)
 except (ValueError,TypeError):return False
 if d<datetime.now(tz).date():return False
 evidence=email_intake.literal_evidence(source["text"],item.get("evidence",""))
 if not evidence:return False
 # Never turn historical or hypothetical meetings into automatic calendar mail.
 if re.search(r"\b(?:si (?:è|e') tenut[ao]|si (?:è|e') svolt[ao]|già (?:avvenut[ao]|svolt[ao]|tenut[ao]|conclus[ao])|annullat[ao]|rinviat[ao]|da concordare|da definire|potremmo|possiamo|potrebbe|proporrei|eventualmente|se .*?va bene|nei prossimi giorni)\b",evidence,re.I):return False
 if item.get("kind")!="appointment":return email_intake.deadline_evidenced(due,evidence)
 if not re.search(r"\b(?:riunione|incontro|appuntamento|colloquio|seduta|convocazione|call|lezione|meeting|webinar|esame|si terrà|si svolgerà|convocat[oa]|fissat[oa])\b",evidence,re.I):return False
 if email_intake.appointment_date(source,evidence,due)!=due:return False
 clock=item.get("appointment_time","")
 if clock:
  times=re.findall(r"\b(?:ore\s+|alle\s+)([01]?\d|2[0-3])[:.]([0-5]\d)\b",evidence,re.I)
  if clock not in [f"{int(h):02d}:{m}" for h,m in times]:return False
 return True

def snapshot(t):
 return hashlib.sha256(json.dumps([t["id"],t["owner_id"],t["title"],t["kind"],t["due_at"],t["scope"]],ensure_ascii=False).encode()).hexdigest()

def enqueue(c,data,row,source,owner,created):
 # Called inside the same transaction as task creation. Never acquire outbound LOCK here.
 cfg=mail.load(data);a=rule(cfg)
 if not valid_rule(cfg) or owner!=a["owner_id"]:return
 if row["sender"].casefold()==cfg["sender"].casefold() or MARKER.casefold() in source["subject"].casefold():return
 received=c.execute("SELECT received_at,rowid FROM cloudflare_mail_inbox WHERE message_hash=?",(row["message_hash"],)).fetchone()
 if not received:return
 # SQLite arrival time is recorded to the second. Never scan already processed messages.
 if received[0]<a["activated_at"] or received[1]<=a.get("arrival_cutoff",0):return
 items=[]
 for tid,item in created:
  if not eligible(item,source,TZ):continue
  t=c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone()
  if t and t["owner_id"]==owner and t["scope"]=="personal" and t["status"]=="review":
   try:ical.parse_due(t["due_at"],TZ)
   except (ValueError,TypeError,OverflowError):continue
   items.append([tid,snapshot(t)])
 if not items:return
 table(c)
 c.execute("INSERT OR IGNORE INTO automatic_ics_queue VALUES(?,?,?,?,?,?,?,'queued','In attesa di invio')",
  (row["source_digest"],row["message_hash"],a["id"],owner,a["recipient"],json.dumps(items),int(time.time())))

def run_one(conn,data):
 # Same lock and rate budget as manual mail. Pending rows are durable across restarts.
 if not mail.LOCK.acquire(blocking=False):return
 try:
  cfg=mail.load(data);a=rule(cfg);now=int(time.time())
  with conn() as c:
   table(c);mail.table(c)
   c.execute("UPDATE automatic_ics_queue SET status='expired',detail='Coda scaduta' WHERE status='queued' AND created_epoch<?",(now-86400,))
   row=c.execute("SELECT * FROM automatic_ics_queue WHERE status='queued' ORDER BY created_epoch,rowid LIMIT 1").fetchone()
   if not row:return
   digest=row["source_digest"]
   def cancel(reason):c.execute("UPDATE automatic_ics_queue SET status='cancelled',detail=? WHERE source_digest=?",(reason,digest))
   if not valid_rule(cfg) or row["rule_id"]!=a["id"] or row["recipient"]!=a["recipient"] or row["owner_id"]!=a["owner_id"]:
    cancel("Regola disattivata o modificata");return
   from . import cloudflare_mail
   inbound=cloudflare_mail.load_config(data)
   if not inbound.get("enabled") or inbound.get("owner_id")!=row["owner_id"]:
    cancel("Ricezione disattivata o proprietario modificato");return
   if not c.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(row["owner_id"],)).fetchone():
    cancel("Amministratore non attivo");return
   if c.execute("SELECT COUNT(*) FROM outbound_mail_log WHERE created_epoch>?",(now-3600,)).fetchone()[0]>=30:return
   if c.execute("SELECT 1 FROM outbound_mail_log WHERE created_epoch>? LIMIT 1",(now-10,)).fetchone():return
   tasks=[]
   for tid,expected in json.loads(row["items"]):
    t=c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone()
    if not t or t["owner_id"]!=row["owner_id"] or t["scope"]!="personal" or t["status"]!="review" or snapshot(t)!=expected:continue
    try:
     due=ical.parse_due(t["due_at"],TZ)
     day=due.astimezone(TZ).date() if isinstance(due,datetime) else due
     if day<datetime.now(TZ).date():continue
    except (ValueError,TypeError,OverflowError):continue
    tasks.append(t)
   if not tasks:cancel("Voci eliminate, modificate, confermate o trascorse");return
   ics=ical.calendar(tasks,TZ,False,tentative=True)
   rid="auto-"+digest
   c.execute("UPDATE automatic_ics_queue SET status='sending',detail='Invio avviato: verificare Cloudflare se rimane in questo stato' WHERE source_digest=?",(digest,))
   c.execute("INSERT INTO outbound_mail_log VALUES(?,?,?,?,?,?,?,?)",(rid,now,row["owner_id"],"auto", "sending",len(tasks),hashlib.sha256(row["recipient"].encode()).hexdigest(),"Invio automatico avviato"))
  # No network inside a DB transaction. If interrupted after claim, never resend automatically.
  try:
   status,detail=mail.provider_send(cfg,row["recipient"],ics,MARKER,
    f"NextDo ha individuato {len(tasks)} attività, scadenze o appuntamenti con data. L'allegato contiene proposte AI DA VERIFICARE, non inviti o conferme. Controllare le date in NextDo prima di farvi affidamento. Nessun testo originale o allegato della mail ricevuta è incluso.")
  except Exception:status,detail="unknown","Esito non certo: verificare Cloudflare"
  with conn() as c:
   c.execute("UPDATE automatic_ics_queue SET status=?,detail=? WHERE source_digest=?",(status,detail,digest))
   c.execute("UPDATE outbound_mail_log SET status=?,detail=? WHERE request_id=?",(status,detail,rid))
   c.execute("DELETE FROM outbound_mail_log WHERE created_epoch<?",(now-90*86400,))
 except Exception:LOG.warning("NextDo automatic ICS processing deferred")
 finally:mail.LOCK.release()

class RuleIn(BaseModel):
 enabled:bool=False
 recipient:str=Field(default="",max_length=254)
 confirmed:bool=False

def register(app,*,conn,user,csrf,data_path):
 def admin(req,write=False):
  u=user(req)
  if u["role"]!="admin":mail.fail("Solo amministratore",403)
  if write:csrf(req)
  return u
 @app.get("/api/outbound-mail/automatic-ics")
 def get_rule(req:Request):
  admin(req)
  with mail.LOCK:result=public(mail.load(data_path))
  with conn() as c:
   table(c)
   result["history"]=[dict(x) for x in c.execute("SELECT message_hash,status,detail,created_epoch FROM automatic_ics_queue ORDER BY created_epoch DESC,rowid DESC LIMIT 30")]
  return result
 @app.post("/api/outbound-mail/automatic-ics")
 def set_rule(b:RuleIn,req:Request):
  u=admin(req,True)
  from . import cloudflare_mail
  with mail.LOCK:
   cfg=mail.load(data_path)
   recipient=b.recipient.strip().lower()
   if b.enabled:
    if not cfg.get("enabled") or not cfg.get("tested") or recipient not in cfg.get("recipients",[]):mail.fail("Abilitare la posta in uscita e scegliere un destinatario verificato")
    incoming=cloudflare_mail.load_config(data_path)
    if not incoming.get("enabled") or incoming.get("owner_id")!=u["id"]:mail.fail("Attivare la ricezione Cloudflare con questo amministratore")
    if not b.confirmed:mail.fail("Confermare l'invio automatico di proposte da verificare")
   if not b.enabled:
    cfg.pop("automatic_ics",None)
   else:
    with conn() as c:cutoff=c.execute("SELECT COALESCE(MAX(rowid),0) FROM cloudflare_mail_inbox").fetchone()[0]
    cfg["automatic_ics"]={"enabled":True,"recipient":recipient,"id":secrets.token_hex(16),"owner_id":u["id"],
      "activated_at":datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),"arrival_cutoff":cutoff}
   mail.save(data_path,cfg)
   with conn() as c:
    table(c)
    c.execute("UPDATE automatic_ics_queue SET status='cancelled',detail='Regola modificata o disattivata' WHERE status='queued'")
    c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,NULL)",(u["id"],"enable_auto_ics" if b.enabled else "disable_auto_ics","outbound_mail"))
   return public(cfg)
