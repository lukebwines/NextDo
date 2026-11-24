"""Explicitly paired, read-only professional agenda; no travel or admin access."""
import hashlib,re,secrets,time
from datetime import datetime,date,timedelta,timezone
from fastapi import HTTPException,Request
from . import work_push

def fail(code,msg):raise HTTPException(code,msg)
def token():return secrets.token_urlsafe(32)
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def hashed(s):
 if not isinstance(s,str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}",s):fail(401,"Credenziale professionale non valida")
 return digest(s)
def ensure(c):
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_pairs(hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,password_hash TEXT NOT NULL,expires REAL NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_devices(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,label TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,expires REAL NOT NULL,created REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)""")
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_alert_tokens(hash TEXT PRIMARY KEY,device_id TEXT NOT NULL UNIQUE REFERENCES work_mobile_devices(id) ON DELETE CASCADE)""")
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_ack(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,revision TEXT NOT NULL,seen REAL NOT NULL,PRIMARY KEY(user_id,task_id))""")
 work_push.ensure(c)
def revision(t):
 return digest(repr(tuple(t[k] for k in ("id","updated_at","due_at","start_at","priority","status","kind","title","description"))))
def seen(c,u,t):
 r=c.execute("SELECT revision,seen FROM work_mobile_ack WHERE user_id=? AND task_id=?",(u["id"],t["id"])).fetchone()
 return r["seen"] if r and r["revision"]==revision(t) else None
def mark(c,u,t):
 c.execute("INSERT OR REPLACE INTO work_mobile_ack VALUES(?,?,?,?)",(u["id"],t["id"],revision(t),time.time()))
def day_info(value,tz):
 if not value:return None,None
 try:
  if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
   return date.fromisoformat(value).isoformat(),None
  dt=datetime.fromisoformat(value.replace("Z","+00:00"))
  dt=(dt if dt.tzinfo else dt.replace(tzinfo=tz)).astimezone(tz)
  return dt.date().isoformat(),dt.isoformat()
 except (ValueError,OverflowError,TypeError):return None,None
def register(app,*,conn,user,csrf,accessible,tz,record,data_path):
 with conn() as c:ensure(c)
 work_push.register(app,conn=conn,user=user,csrf=csrf,accessible=accessible,data_path=data_path,revision=revision,seen=seen)
 def credentials(c,uid):
  row=c.execute("SELECT id,username,display_name,role,active,password FROM users WHERE id=?",(uid,)).fetchone()
  if not row or not row["active"]:fail(401,"Account non disponibile")
  return row
 def auth(c,req):
  h=req.headers.get("authorization","")
  if not h.startswith("Bearer "):fail(401,"Associazione professionale richiesta")
  ensure(c)
  d=c.execute("SELECT * FROM work_mobile_devices WHERE hash=? AND revoked=0 AND expires>?",(hashed(h[7:]),time.time())).fetchone()
  if not d:fail(401,"Associazione scaduta o revocata")
  u=credentials(c,d["user_id"])
  if not secrets.compare_digest(d["password_hash"],digest(u["password"])):fail(401,"Credenziali cambiate: riassociare il dispositivo")
  return u,d
 def alert_auth(c,req):
  h=req.headers.get("authorization","")
  if not h.startswith("Bearer "):fail(401,"Autorizzazione avvisi richiesta")
  ensure(c)
  d=c.execute("""SELECT d.* FROM work_mobile_alert_tokens a JOIN work_mobile_devices d ON d.id=a.device_id WHERE a.hash=? AND d.revoked=0 AND d.expires>?""",(hashed(h[7:]),time.time())).fetchone()
  if not d:fail(401,"Autorizzazione avvisi scaduta o revocata")
  u=credentials(c,d["user_id"])
  if not secrets.compare_digest(d["password_hash"],digest(u["password"])):fail(401,"Credenziali cambiate")
  return u,d
 def allowed_task(c,u,tid):
  t=c.execute("SELECT * FROM tasks WHERE id=? AND kind IN ('task','appointment')",(tid,)).fetchone()
  if not t or not accessible(c,u,t):fail(404,"Voce non disponibile")
  return t
 def key_for(d,t):
  # Preserve identifiers already issued by 0.1.40 for offline acknowledgement.
  return digest(d["id"]+":"+str(t["id"])+":"+str(t["updated_at"])+":"+str(t["due_at"])+":"+t["priority"]+":"+t["status"]+":"+t["kind"])
 @app.post("/api/work-mobile/ack/{tid}")
 def web_ack(tid:int,req:Request,b:dict):
  u=user(req);csrf(req)
  with conn() as c:
   ensure(c);t=allowed_task(c,u,tid)
   if b.get("revision")!=revision(t):fail(409,"Voce modificata: aggiorna prima di confermare")
   mark(c,u,t);record(c,u["id"],"work_ack","task",tid)
  return {"ok":True}
 @app.post("/api/mobile/v1/work/agenda/{tid}/ack")
 def mobile_ack(tid:int,req:Request,b:dict):
  with conn() as c:
   u,d=auth(c,req);t=allowed_task(c,u,tid)
   if b.get("revision")!=revision(t):fail(409,"Voce modificata: aggiorna prima di confermare")
   mark(c,u,t);record(c,u["id"],"work_ack","task",tid)
  return {"ok":True}
 @app.post("/api/mobile/v1/work/alerts/ack")
 def alert_ack(req:Request,b:dict):
  key=b.get("key")
  if not isinstance(key,str) or not re.fullmatch(r"[a-f0-9]{64}",key):fail(400,"Avviso non valido")
  with conn() as c:
   u,d=alert_auth(c,req)
   for t in c.execute("SELECT * FROM tasks WHERE kind IN ('task','appointment') AND status!='done'"):
    if key_for(d,t)==key and accessible(c,u,t):
     mark(c,u,t);record(c,u["id"],"work_ack","task",t["id"])
     return {"ok":True}
   fail(404,"Avviso non più disponibile")
 @app.get("/api/mobile/v1/work/alerts/push/config")
 def push_config(req:Request):
  with conn() as c:alert_auth(c,req)
  return {"config":work_push.public_config(data_path)}
 @app.post("/api/mobile/v1/work/alerts/push/register")
 def push_register(req:Request,b:dict):
  config=work_push.public_config(data_path)
  if not config:fail(409,"Push non configurato")
  value=b.get("token")
  if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_:.\-]{20,4096}",value):fail(400,"Token push non valido")
  if b.get("project_id")!=config["project_id"]:fail(409,"Configurazione push cambiata")
  with conn() as c:
   u,d=alert_auth(c,req)
   work_push.subscribe(c,d["id"],value,config["project_id"])
  return {"ok":True}
 @app.post("/api/work-mobile/pair")
 def create_pair(req:Request):
  u=user(req);csrf(req);raw=token()
  with conn() as c:
   ensure(c);account=credentials(c,u["id"])
   c.execute("DELETE FROM work_mobile_pairs WHERE expires<=? OR user_id=?",(time.time(),u["id"]))
   c.execute("INSERT INTO work_mobile_pairs VALUES(?,?,?,?)",(digest(raw),u["id"],digest(account["password"]),time.time()+300))
   record(c,u["id"],"mobile_pair_created","work_mobile",None)
  return {"code":raw,"expires_in":300}
 @app.get("/api/work-mobile/devices")
 def devices(req:Request):
  u=user(req)
  with conn() as c:
   ensure(c)
   return [dict(x) for x in c.execute("SELECT id,label,created,expires,revoked FROM work_mobile_devices WHERE user_id=? ORDER BY created DESC",(u["id"],))]
 @app.post("/api/work-mobile/devices/{did}/revoke")
 def revoke(did:str,req:Request):
  u=user(req);csrf(req)
  with conn() as c:
   ensure(c)
   if not c.execute("UPDATE work_mobile_devices SET revoked=1 WHERE id=? AND user_id=?",(did,u["id"])).rowcount:fail(404,"Dispositivo non trovato")
   record(c,u["id"],"mobile_revoked","work_mobile",None)
  return {"ok":True}
 @app.post("/api/mobile/v1/work/pair")
 def pair(b:dict):
  code=hashed(b.get("code"));label=b.get("label","Android")
  if not isinstance(label,str) or not label.strip() or len(label)>80:fail(400,"Nome dispositivo non valido")
  now=time.time();raw=token();did=secrets.token_hex(16)
  with conn() as c:
   ensure(c);p=c.execute("SELECT * FROM work_mobile_pairs WHERE hash=? AND expires>?",(code,now)).fetchone()
   if not p:fail(401,"Codice scaduto o non valido")
   u=credentials(c,p["user_id"])
   if not secrets.compare_digest(p["password_hash"],digest(u["password"])):fail(401,"Codice non più valido")
   c.execute("DELETE FROM work_mobile_pairs WHERE hash=?",(code,))
   c.execute("INSERT INTO work_mobile_devices(id,user_id,label,hash,password_hash,expires,created) VALUES(?,?,?,?,?,?,?)",(did,u["id"],label.strip(),digest(raw),digest(u["password"]),now+30*86400,now))
   record(c,u["id"],"mobile_paired","work_mobile",None)
  return {"device_token":raw,"expires_in":30*86400,"display_name":u["display_name"]}
 @app.post("/api/mobile/v1/work/revoke")
 def revoke_self(req:Request):
  with conn() as c:
   u,d=auth(c,req);c.execute("UPDATE work_mobile_devices SET revoked=1 WHERE id=?",(d["id"],))
   record(c,u["id"],"mobile_revoked","work_mobile",None)
  return {"ok":True}
 @app.get("/api/mobile/v1/work/agenda")
 def agenda(req:Request,after:int=0):
  if after<0:fail(400,"Cursore non valido")
  with conn() as c:
   u,d=auth(c,req)
   now=datetime.now(tz);today=now.date();monday=today-timedelta(days=today.weekday())
   rows=[]
   for t in c.execute("SELECT * FROM tasks WHERE id>? AND kind IN ('task','appointment') AND status!='done' ORDER BY id",(after,)):
    if not accessible(c,u,t):continue
    day,instant=day_info(t["due_at"],tz)
    overdue=False
    if day:
     overdue=day<today.isoformat() if not instant else datetime.fromisoformat(instant)<now
    rows.append({"id":t["id"],"title":t["title"],"kind":t["kind"],"priority":t["priority"],"status":t["status"],"due_at":t["due_at"],"day":day,"instant":instant,"overdue":overdue,"updated_at":t["updated_at"],"revision":revision(t),"acknowledged":seen(c,u,t) is not None})
    if len(rows)>200:break
   more=len(rows)>200;rows=rows[:200]
   return {"items":rows,"next_after":rows[-1]["id"] if more else None,"today":today.isoformat(),"week_start":monday.isoformat(),"timezone":str(tz),"updated_at":now.isoformat(),"display_name":u["display_name"]}
 @app.get("/api/mobile/v1/work/agenda/{tid}")
 def detail(tid:int,req:Request):
  with conn() as c:
   u,d=auth(c,req);t=c.execute("SELECT * FROM tasks WHERE id=? AND kind IN ('task','appointment')",(tid,)).fetchone()
   if not t or not accessible(c,u,t):fail(404,"Voce non disponibile")
   return {"id":t["id"],"title":t["title"],"description":t["description"] or "","kind":t["kind"],"status":t["status"],"priority":t["priority"],"due_at":t["due_at"],"start_at":t["start_at"],"revision":revision(t),"acknowledged":seen(c,u,t) is not None}

 @app.post("/api/mobile/v1/work/alerts/enable")
 def enable_alerts(req:Request):
  raw=token()
  with conn() as c:
   u,d=auth(c,req)
   c.execute("DELETE FROM work_mobile_alert_tokens WHERE device_id=?",(d["id"],))
   c.execute("DELETE FROM work_mobile_push WHERE device_id=?",(d["id"],))
   c.execute("INSERT INTO work_mobile_alert_tokens VALUES(?,?)",(digest(raw),d["id"]))
   return {"alert_token":raw,"expires":d["expires"]}
 @app.post("/api/mobile/v1/work/alerts/disable")
 def disable_alerts(req:Request):
  with conn() as c:
   u,d=auth(c,req)
   c.execute("DELETE FROM work_mobile_alert_tokens WHERE device_id=?",(d["id"],))
   c.execute("DELETE FROM work_mobile_push WHERE device_id=?",(d["id"],))
  return {"ok":True}
 @app.get("/api/mobile/v1/work/alerts")
 def alerts(req:Request,after:int=0):
  if after<0:fail(400,"Cursore non valido")
  with conn() as c:
   u,d=alert_auth(c,req)
   rows=[]
   now=datetime.now(tz)
   for t in c.execute("SELECT * FROM tasks WHERE id>? AND kind IN ('task','appointment') AND status!='done' ORDER BY id",(after,)):
    if not accessible(c,u,t):continue
    day,instant=day_info(t["due_at"],tz)
    # A date-only reminder is explicitly a reminder at 09:00, never an appointment time.
    when=None
    if instant:when=datetime.fromisoformat(instant)
    elif day:when=datetime.combine(date.fromisoformat(day),datetime.min.time().replace(hour=9),tzinfo=tz)
    # Opaque per-device, per-revision key; never send title, description, person, or source.
    key=key_for(d,t)
    rows.append((t["id"],{"key":key,"kind":t["kind"],"priority":t["priority"],"review":t["status"]=="review","when":int(when.timestamp()) if when else None,"date_only":bool(day and not instant),"acknowledged":seen(c,u,t) is not None}))
    if len(rows)>200:break
   more=len(rows)>200;rows=rows[:200]
   return {"items":[a for _,a in rows],"next_after":rows[-1][0] if more else None,"expires":d["expires"]}
