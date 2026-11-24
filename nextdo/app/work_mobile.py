"""Explicitly paired, read-only professional agenda; no travel or admin access."""
import hashlib,re,secrets,time
from datetime import datetime,date,timedelta,timezone
from fastapi import HTTPException,Request

def fail(code,msg):raise HTTPException(code,msg)
def token():return secrets.token_urlsafe(32)
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def hashed(s):
 if not isinstance(s,str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}",s):fail(401,"Credenziale professionale non valida")
 return digest(s)
def ensure(c):
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_pairs(hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,password_hash TEXT NOT NULL,expires REAL NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_devices(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,label TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,expires REAL NOT NULL,created REAL NOT NULL,revoked INTEGER NOT NULL DEFAULT 0)""")
def day_info(value,tz):
 if not value:return None,None
 try:
  if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
   return date.fromisoformat(value).isoformat(),None
  dt=datetime.fromisoformat(value.replace("Z","+00:00"))
  dt=(dt if dt.tzinfo else dt.replace(tzinfo=tz)).astimezone(tz)
  return dt.date().isoformat(),dt.isoformat()
 except (ValueError,OverflowError,TypeError):return None,None
def register(app,*,conn,user,csrf,accessible,tz,record):
 with conn() as c:ensure(c)
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
    rows.append({"id":t["id"],"title":t["title"],"kind":t["kind"],"priority":t["priority"],"status":t["status"],"due_at":t["due_at"],"day":day,"instant":instant,"overdue":overdue,"updated_at":t["updated_at"]})
    if len(rows)>200:break
   more=len(rows)>200;rows=rows[:200]
   return {"items":rows,"next_after":rows[-1]["id"] if more else None,"today":today.isoformat(),"week_start":monday.isoformat(),"timezone":str(tz),"updated_at":now.isoformat(),"display_name":u["display_name"]}
 @app.get("/api/mobile/v1/work/agenda/{tid}")
 def detail(tid:int,req:Request):
  with conn() as c:
   u,d=auth(c,req);t=c.execute("SELECT * FROM tasks WHERE id=? AND kind IN ('task','appointment')",(tid,)).fetchone()
   if not t or not accessible(c,u,t):fail(404,"Voce non disponibile")
   return {"id":t["id"],"title":t["title"],"description":t["description"] or "","kind":t["kind"],"status":t["status"],"priority":t["priority"],"due_at":t["due_at"],"start_at":t["start_at"]}
