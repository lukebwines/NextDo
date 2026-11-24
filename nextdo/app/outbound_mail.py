"""Cloudflare Email Sending, independent of inbound routing. Manual administrator-only sending."""
from __future__ import annotations
import base64, json, os, re, secrets, threading, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import request, error
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from . import calendar_export, email_intake

LOCK=threading.Lock()
ACCOUNT=re.compile(r"[a-fA-F0-9]{32}\Z")
ADDRESS=re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\Z")
REQUEST_ID=re.compile(r"[a-fA-F0-9-]{32,36}\Z")
MAX_ICS=5_000_000
def fail(message,code=400):raise HTTPException(code,message)
def valid_address(s):return len(s)<=254 and bool(ADDRESS.fullmatch(s))
def path(data):return Path(data)/"outbound-mail-local.json"
def load(data):
 if not path(data).exists():return {}
 try:
  d=json.loads(path(data).read_text(encoding="utf-8"))
  if not isinstance(d,dict):raise ValueError()
  if d.get("token"):
   if not d["token"].startswith("enc:"):raise ValueError()
   d["token"]=email_intake._cipher(data).decrypt(d["token"][4:].encode()).decode()
  return d
 except Exception:fail("Configurazione posta in uscita non leggibile",500)
def save(data,cfg):
 d=dict(cfg)
 if d.get("token"):d["token"]="enc:"+email_intake._cipher(data).encrypt(d["token"].encode()).decode()
 target=path(data);tmp=target.with_name(target.name+"."+secrets.token_hex(8)+".tmp")
 try:
  fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as stream:json.dump(d,stream,ensure_ascii=False)
  os.replace(tmp,target)
 finally:tmp.unlink(missing_ok=True)
def public(cfg):
 return {"provider":"cloudflare","account_id":cfg.get("account_id",""),"sender":cfg.get("sender",""),
  "recipients":cfg.get("recipients",[]),"token_configured":bool(cfg.get("token")),
  "tested":bool(cfg.get("tested")),"enabled":bool(cfg.get("enabled"))}
class Config(BaseModel):
 account_id:str=Field(default="",max_length=32)
 sender:str=Field(default="",max_length=254)
 recipients:list[str]=Field(default_factory=list,max_length=200)
 token:str=Field(default="",max_length=512)
class Enable(BaseModel):
 enabled:bool
 confirmed_received:bool=False
class SendTest(BaseModel):
 recipient:str=Field(max_length=254)
 request_id:str=Field(max_length=36)
class SendICS(SendTest):
 task_ids:list[int]=Field(min_length=1,max_length=500)
 include_details:bool=False
 confirmed:bool=False

class NoRedirect(request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def provider_send(cfg,recipient,ics,subject,body):
 if len(ics.encode("utf-8"))>MAX_ICS:fail("File ICS troppo grande: ridurre la selezione")
 payload={"to":recipient,"from":cfg["sender"],"subject":subject,"text":body,
  "attachments":[{"filename":"nextdo-calendario.ics","type":"text/calendar","disposition":"attachment","content":base64.b64encode(ics.encode("utf-8")).decode("ascii")}]}
 url="https://api.cloudflare.com/client/v4/accounts/"+cfg["account_id"]+"/email/sending/send"
 req=request.Request(url,data=json.dumps(payload,ensure_ascii=False).encode(),headers={
  "Authorization":"Bearer "+cfg["token"],"Content-Type":"application/json","User-Agent":"NextDo/0.1.44-test"},method="POST")
 try:
  with request.build_opener(NoRedirect()).open(req,timeout=30) as response:
   raw=response.read(1_000_001)
   if len(raw)>1_000_000:raise ValueError()
   data=json.loads(raw)
 except error.HTTPError as e:
  # Do not echo provider bodies, credentials, message or recipient in errors.
  code=e.code
  if code in (400,401,403,404,429):return ("rejected","Cloudflare HTTP "+str(code))
  return ("unknown","Esito non certo (HTTP "+str(code)+"): verificare il registro Cloudflare prima di riprovare")
 except Exception:
  return ("unknown","Esito non certo: verificare il registro Cloudflare prima di riprovare")
 if not isinstance(data,dict):return ("unknown","Risposta Cloudflare non riconosciuta")
 if data.get("success") is not True:return ("rejected","Richiesta rifiutata da Cloudflare")
 result=data.get("result")
 if not isinstance(result,dict):return ("unknown","Risposta Cloudflare incompleta")
 for key,status,label in (("permanent_bounces","bounced","Mancata consegna"),("suppressed_recipients","suppressed","Destinatario soppresso"),("delivered","delivered","Consegnata secondo Cloudflare"),("queued","queued","Accodata da Cloudflare")):
  values=result.get(key,[])
  if isinstance(values,list) and any(isinstance(x,str) and x.lower()==recipient.lower() for x in values):return (status,label)
 return ("unknown","Risposta senza esito per il destinatario: verificare Cloudflare")

def table(c):
 c.execute("""CREATE TABLE IF NOT EXISTS outbound_mail_log(
 request_id TEXT PRIMARY KEY,created_epoch INTEGER NOT NULL,actor_id INTEGER NOT NULL,
 kind TEXT NOT NULL,status TEXT NOT NULL,task_count INTEGER NOT NULL,recipient_hash TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT '')""")

def synthetic(tz):
 tomorrow=(datetime.now(tz).date()+timedelta(days=1)).isoformat()
 return calendar_export.calendar([{"id":0,"owner_id":0,"created_at":"test","title":"NextDo - evento fittizio di prova",
 "description":"","kind":"appointment","status":"todo","due_at":tomorrow}],tz)

def register(app,*,conn,user,csrf,accessible,tz,data_path,record):
 def admin(req,write=False):
  u=user(req)
  if u["role"]!="admin":fail("Funzione riservata all'amministratore",403)
  if write:csrf(req)
  return u
 @app.get("/api/outbound-mail/config")
 def get_config(req:Request):
  admin(req)
  with LOCK:return public(load(data_path))
 @app.post("/api/outbound-mail/config")
 def set_config(b:Config,req:Request):
  u=admin(req,True)
  account=b.account_id.strip().lower();sender=b.sender.strip().lower()
  recipients=list(dict.fromkeys(x.strip().lower() for x in b.recipients if x.strip()))
  if not ACCOUNT.fullmatch(account) or not valid_address(sender) or not recipients or any(not valid_address(x) for x in recipients):fail("Verificare Account ID, mittente e destinatari autorizzati")
  token=b.token.strip()
  if token and not re.fullmatch(r"[A-Za-z0-9_\-]+",token):fail("Token API non valido")
  with LOCK:
   old=load(data_path)
   if not token and old.get("account_id")==account:token=old.get("token","")
   if not token:fail("Inserire il token Cloudflare")
   cfg={"account_id":account,"sender":sender,"recipients":recipients,"token":token,"enabled":False,"tested":False}
   save(data_path,cfg)
  with conn() as c:record(c,u["id"],"configure","outbound_mail",None)
  return public(cfg)
 @app.post("/api/outbound-mail/enable")
 def enable(b:Enable,req:Request):
  u=admin(req,True)
  with LOCK:
   cfg=load(data_path)
   if b.enabled and (not cfg.get("tested") or not b.confirmed_received):fail("Confermare la ricezione e apertura del file ICS di prova")
   cfg["enabled"]=b.enabled
   if not b.enabled:cfg.pop("automatic_ics",None)
   save(data_path,cfg)
  with conn() as c:record(c,u["id"],"enable" if b.enabled else "disable","outbound_mail",None)
  return public(cfg)
 @app.get("/api/outbound-mail/history")
 def history(req:Request):
  admin(req)
  with conn() as c:
   table(c)
   return [dict(r) for r in c.execute("SELECT created_epoch,kind,status,task_count,detail FROM outbound_mail_log ORDER BY created_epoch DESC,rowid DESC LIMIT 50")]
 def send(b,req,test):
  import hashlib
  u=admin(req,True)
  recipient=b.recipient.strip().lower()
  if not REQUEST_ID.fullmatch(b.request_id):fail("Identificativo invio non valido")
  with LOCK:
   cfg=load(data_path)
   if not cfg.get("token") or not cfg.get("account_id"):fail("Configurare prima la posta in uscita")
   if recipient not in cfg.get("recipients",[]):fail("Destinatario non autorizzato",403)
   if not test and (not cfg.get("enabled") or not cfg.get("tested")):fail("Eseguire il collaudo e abilitare la posta in uscita",409)
   if not test and not b.confirmed:fail("Confermare esplicitamente l'invio")
   now=int(time.time())
   with conn() as c:
    table(c)
    prior=c.execute("SELECT status,detail FROM outbound_mail_log WHERE request_id=?",(b.request_id,)).fetchone()
    if prior:return {"status":prior["status"],"detail":prior["detail"],"duplicate":True}
    if c.execute("SELECT COUNT(*) FROM outbound_mail_log WHERE created_epoch>?",(now-3600,)).fetchone()[0]>=30:fail("Limite NextDo: 30 invii all'ora",429)
    if c.execute("SELECT 1 FROM outbound_mail_log WHERE created_epoch>? LIMIT 1",(now-10,)).fetchone():fail("Attendere almeno 10 secondi tra gli invii",429)
    selected=[]
    if test:ics=synthetic(tz)
    else:
     for tid in dict.fromkeys(b.task_ids):
      t=c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone()
      if not t or not accessible(c,u,t):fail("Una delle attività non è disponibile",403)
      if not calendar_export.eligible(t,tz):fail("Selezionare attività confermate con data valida")
      selected.append(t)
     try:ics=calendar_export.calendar(selected,tz,b.include_details)
     except (ValueError,OverflowError):fail("Data non esportabile")
    if len(ics.encode("utf-8"))>MAX_ICS:fail("File ICS troppo grande: ridurre la selezione")
    c.execute("INSERT INTO outbound_mail_log VALUES(?,?,?,?,?,?,?,?)",(b.request_id,now,u["id"],"test" if test else "ics","sending",len(selected),hashlib.sha256(recipient.encode()).hexdigest(),"Invio avviato: verificare Cloudflare se rimane in questo stato"))
    c.execute("DELETE FROM outbound_mail_log WHERE created_epoch<?",(now-90*86400,))
   status,detail=provider_send(cfg,recipient,ics,"NextDo - prova ICS" if test else "NextDo - calendario ICS",
    "Messaggio di collaudo con evento fittizio. Aprire l'allegato ICS." if test else "In allegato le voci di calendario selezionate in NextDo. Importare il file nel calendario desiderato.")
   with conn() as c:
    c.execute("UPDATE outbound_mail_log SET status=?,detail=? WHERE request_id=?",(status,detail,b.request_id))
    record(c,u["id"],"send_"+status,"outbound_mail",None)
   if test and status in ("delivered","queued"):
    cfg["tested"]=True;save(data_path,cfg)
   return {"status":status,"detail":detail,"duplicate":False}
 @app.post("/api/outbound-mail/test")
 def test_mail(b:SendTest,req:Request):return send(b,req,True)
 @app.post("/api/outbound-mail/send-ics")
 def send_ics(b:SendICS,req:Request):return send(b,req,False)
