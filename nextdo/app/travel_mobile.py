"""Device-scoped travel API. Pairing requires an unlocked web account."""
from . import travel_timeline
import hashlib,secrets,re,time
from datetime import date
from fastapi import Request,HTTPException
from fastapi.responses import Response,JSONResponse
from argon2.exceptions import VerificationError

def fail(code,message):raise HTTPException(code,message)
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def token():return secrets.token_urlsafe(32)
def raw_token(value):
 if not isinstance(value,str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}",value):fail(401,"Credenziale non valida")
 return digest(value)

def register(app,*,db,mutex,conn,allowed,ph,load,read_archive,save,new_manifest,limit,import_bundle,export_bundle,map_tile,data_path):
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS mobile_pairings(code_hash TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS mobile_devices(id TEXT PRIMARY KEY,owner TEXT NOT NULL,label TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,expires REAL NOT NULL,created REAL NOT NULL,revoked INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS mobile_sessions(token_hash TEXT PRIMARY KEY,device_id TEXT NOT NULL,expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS mobile_trust(device_id TEXT PRIMARY KEY,token_hash TEXT NOT NULL,expires REAL NOT NULL);
  CREATE TABLE IF NOT EXISTS private_alert_tokens(device_id TEXT PRIMARY KEY,token_hash TEXT UNIQUE NOT NULL);
  """)
 def active(owner):
  with conn() as c:
   row=c.execute("SELECT 1 FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE p.owner=? AND u.active=1",(owner,)).fetchone()
  if not row:fail(401,"Account non disponibile")
 def clean(c):
  now=time.time()
  c.execute("DELETE FROM mobile_pairings WHERE expires<=?",(now,))
  c.execute("DELETE FROM mobile_sessions WHERE expires<=?",(now,))
  c.execute("DELETE FROM mobile_trust WHERE expires<=?",(now,))
 def auth(req,session=True):
  h=req.headers.get("authorization","")
  if not h.startswith("Bearer "):fail(401,"Accesso dispositivo richiesto")
  hashed=raw_token(h[7:])
  with db() as c:
   if session:
    row=c.execute("SELECT d.* FROM mobile_sessions s JOIN mobile_devices d ON d.id=s.device_id WHERE s.token_hash=? AND s.expires>? AND d.expires>? AND d.revoked=0",(hashed,time.time(),time.time())).fetchone()
   else:row=c.execute("SELECT * FROM mobile_devices WHERE token_hash=? AND expires>? AND revoked=0",(hashed,time.time())).fetchone()
  if not row:fail(401,"Sessione scaduta o dispositivo revocato")
  active(row["owner"])
  return row
 from . import private_items
 with conn() as c:private_items.ensure(c)
 private_items.register(app,conn,allowed,lambda req,write:auth(req)["owner"],data_path)
 from . import private_alerts
 private_alerts.register(app,db,conn,auth,active,token,digest,raw_token)
 travel_timeline.register(app,db=db,allowed=allowed,auth=auth,load=load,map_tile=map_tile)
 @app.get('/api/mobile/v1/assistant-link')
 def assistant_pref(req:Request):
  from . import assistant_link
  owner=auth(req)['owner']
  with conn() as c:
   row=c.execute('SELECT u.id FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE p.owner=? AND u.active=1',(owner,)).fetchone()
   if not row:fail(401,'Account non disponibile')
   return assistant_link.get(c,row['id'])
 @app.get("/api/personal/mobile/devices")
 def devices(req:Request):
  owner=allowed(req)
  with db() as c:return [dict(r) for r in c.execute("SELECT id,label,expires,created,revoked FROM mobile_devices WHERE owner=? ORDER BY created DESC",(owner,))]
 @app.post("/api/personal/mobile/pair")
 def create_pair(req:Request):
  owner=allowed(req,True);raw=token()
  with db() as c:
   clean(c);c.execute("DELETE FROM mobile_pairings WHERE owner=?",(owner,))
   c.execute("INSERT INTO mobile_pairings VALUES(?,?,?)",(digest(raw),owner,time.time()+300))
  return {"code":raw,"expires_in":300}
 @app.post("/api/personal/mobile/devices/{device_id}/revoke")
 def revoke(device_id:str,req:Request):
  owner=allowed(req,True)
  with db() as c:
   r=c.execute("UPDATE mobile_devices SET revoked=1 WHERE id=? AND owner=?",(device_id,owner))
   if not r.rowcount:fail(404,"Dispositivo non trovato")
   c.execute("DELETE FROM mobile_sessions WHERE device_id=?",(device_id,))
   c.execute("DELETE FROM mobile_trust WHERE device_id=?",(device_id,))
   c.execute("DELETE FROM private_alert_tokens WHERE device_id=?",(device_id,))
  return {"ok":True}
 @app.post("/api/mobile/v1/pair")
 def pair(b:dict):
  hashed=raw_token(b.get("code"));label=b.get("label","Android")
  if not isinstance(label,str) or not label.strip() or len(label)>80:fail(400,"Nome dispositivo non valido")
  with db() as c:r=c.execute("SELECT owner FROM mobile_pairings WHERE code_hash=? AND expires>?",(hashed,time.time())).fetchone()
  if not r:fail(401,"Codice scaduto o non valido")
  owner=r["owner"];active(owner)
  raw=token();device=secrets.token_hex(16);now=time.time()
  with db() as c:
   clean(c)
   if not c.execute("DELETE FROM mobile_pairings WHERE code_hash=? AND owner=? AND expires>?",(hashed,owner,now)).rowcount:fail(401,"Codice già utilizzato")
   c.execute("INSERT INTO mobile_devices(id,owner,label,token_hash,expires,created) VALUES(?,?,?,?,?,?)",(device,owner,label.strip(),digest(raw),now+30*86400,now))
  return {"device_token":raw,"device_id":device,"expires_in":30*86400}
 @app.post("/api/mobile/v1/unlock")
 def unlock(req:Request,b:dict):
  device=auth(req,False);owner=device["owner"];pin=b.get("pin")
  if not isinstance(pin,str) or not re.fullmatch(r"[0-9]{4,12}",pin):fail(400,"PIN da 4 a 12 cifre richiesto")
  error=None;raw=token();remember=token() if b.get("remember") is True else None
  with db() as c:
   r=c.execute("SELECT * FROM pins WHERE owner=?",(owner,)).fetchone()
   if not r:fail(403,"Impostare il PIN dall'area personale web")
   if r["blocked_until"]>time.time():error=(429,"Troppi tentativi. Riprovare tra 5 minuti")
   else:
    try:ok=ph.verify(r["pin"],pin)
    except VerificationError:ok=False
    if not ok:
     n=r["attempts"]+1
     c.execute("UPDATE pins SET attempts=?,blocked_until=? WHERE owner=?",(0 if n>=5 else n,time.time()+300 if n>=5 else 0,owner))
     error=(403,"PIN non corretto")
    else:
     c.execute("UPDATE pins SET attempts=0,blocked_until=0 WHERE owner=?",(owner,))
     clean(c)
     if not c.execute("SELECT 1 FROM mobile_devices WHERE id=? AND revoked=0 AND expires>?",(device["id"],time.time())).fetchone():fail(401,"Dispositivo non autorizzato")
     if remember:
      c.execute("INSERT OR REPLACE INTO mobile_trust VALUES(?,?,?)",(device["id"],digest(remember),min(device["expires"],time.time()+30*86400)))
     else:c.execute("DELETE FROM mobile_trust WHERE device_id=?",(device["id"],))
     c.execute("DELETE FROM mobile_sessions WHERE device_id=?",(device["id"],))
     c.execute("INSERT INTO mobile_sessions VALUES(?,?,?)",(digest(raw),device["id"],time.time()+300))
  if error:fail(*error)
  result={"session_token":raw,"expires_in":300}
  if remember:result["remember_token"]=remember
  return result
 @app.post("/api/mobile/v1/resume")
 def resume(req:Request,b:dict):
  device=auth(req,False);hashed=raw_token(b.get("remember_token"));raw=token()
  with db() as c:
   clean(c)
   row=c.execute("SELECT t.token_hash FROM mobile_trust t JOIN mobile_devices d ON d.id=t.device_id WHERE t.device_id=? AND t.expires>? AND d.expires>? AND d.revoked=0",(device["id"],time.time(),time.time())).fetchone()
   if not row or not secrets.compare_digest(row["token_hash"],hashed):fail(401,"Verifica PIN NextDo necessaria")
   c.execute("DELETE FROM mobile_sessions WHERE device_id=?",(device["id"],))
   c.execute("INSERT INTO mobile_sessions VALUES(?,?,?)",(digest(raw),device["id"],time.time()+300))
  return {"session_token":raw,"expires_in":300}
 @app.post("/api/mobile/v1/lock")
 def lock(req:Request):
  device=auth(req)
  with db() as c:c.execute("DELETE FROM mobile_sessions WHERE device_id=?",(device["id"],))
  return {"ok":True}
 @app.get("/api/mobile/v1/appearance")
 def get_appearance(req:Request):
  from . import personal_appearance
  owner=auth(req)["owner"]
  with db() as c:return personal_appearance.get(c,owner)
 @app.post("/api/mobile/v1/appearance")
 def save_appearance(req:Request,b:dict):
  from . import personal_appearance
  owner=auth(req)["owner"]
  with db() as c:return personal_appearance.save(c,owner,b)
 @app.post("/api/mobile/v1/appearance/photo")
 def appearance_photo(req:Request,b:dict):
  from . import personal_appearance
  owner=auth(req)["owner"]
  raw=personal_appearance.decode_mobile_photo(b)
  with db() as c:return personal_appearance.save_photo(c,owner,raw)
 @app.get("/api/mobile/v1/trips")
 def trips(req:Request):
  owner=auth(req)["owner"]
  with db() as c:return [dict(x) for x in c.execute("SELECT id,title,start,end,revision FROM trips WHERE owner=? ORDER BY start DESC",(owner,))]
 @app.post("/api/mobile/v1/trips/import")
 async def import_mobile(req:Request):
  auth(req)
  if req.headers.get("content-type","").split(";")[0]!="application/zip":fail(415,"Richiesto archivio ZIP")
  raw=bytearray()
  async for chunk in req.stream():
   if len(raw)+len(chunk)>limit:fail(413,"Archivio oltre 32 MB")
   raw.extend(chunk)
  # Validate the same package format as the web import; keep blocking ZIP/SQLite off the event loop.
  from starlette.concurrency import run_in_threadpool
  def finish():
   m,state,files,timeline=read_archive(bytes(raw),with_timeline=True)
   with db() as c:
    owner=auth(req)["owner"]
    rev=import_bundle(c,owner,m,state,files,timeline)
   return {"id":m["trip"]["id"],"revision":rev}
  return await run_in_threadpool(finish)
 @app.post("/api/mobile/v1/trips")
 def create_mobile(req:Request,b:dict):
  m=new_manifest(b)
  with db() as c:
   owner=auth(req)["owner"]
   rev=save(c,owner,m,{"notes":{},"checks":{}},{})
  return {"id":m["trip"]["id"],"revision":rev}
 @app.post("/api/mobile/v1/trips/{tid}/edit")
 def edit_mobile(tid:str,req:Request,b:dict):
  rev=b.get("revision");kind=b.get("kind");fields=b.get("fields")
  if type(rev)!=int or not isinstance(fields,dict):fail(400,"Modifica non valida")
  allowed_fields={"trip":{"title","subtitle"},"day":{"place","headline","description"},"event":{"time","title","details"},"booking":{"title","type","date","place","status","ref","price"}}
  if not isinstance(kind,str) or kind not in allowed_fields or not fields or set(fields)-allowed_fields[kind]:fail(400,"Campi non modificabili")
  if any(not isinstance(v,str) or len(v)>20000 or "\x00" in v for v in fields.values()):fail(400,"Testo non valido")
  with db() as c:
   owner=auth(req)["owner"];r=load(c,owner,tid)
   if r["revision"]!=rev:fail(409,"Il viaggio è stato modificato: ricaricare")
   m,state,files=read_archive(r["archive"])
   if kind=="trip":target=m["trip"]
   elif kind in ("day","event"):
    day=next((d for d in m.get("days",[]) if d["date"]==b.get("date")),None)
    if day is None:fail(404,"Giornata non trovata")
    if kind=="day":target=day
    else:
     events=day.setdefault("events",[]);idx=b.get("index")
     if idx is None:
      target={};events.append(target)
     elif type(idx)==int and 0<=idx<len(events):target=events[idx]
     else:fail(404,"Evento non trovato")
   else:
    bookings=m.setdefault("bookings",[]);ident=b.get("id")
    if ident is None:
     target={"id":"booking-"+secrets.token_hex(8),"lines":[],"fields":[],"locations":[]}
     bookings.append(target)
    else:
     target=next((x for x in bookings if x["id"]==ident),None)
     if target is None:fail(404,"Prenotazione non trovata")
   target.update(fields)
   if kind in ("trip","event","booking") and not str(target.get("title","")).strip():fail(400,"Titolo obbligatorio")
   revision=save(c,owner,m,state,files,rev)
  return {"revision":revision,"manifest":m,"state":state}
 @app.get("/api/mobile/v1/trips/{tid}")
 def trip(tid:str,req:Request):
  owner=auth(req)["owner"]
  with db() as c:
   r=load(c,owner,tid);m,state,_=read_archive(r["archive"])
   return {"manifest":m,"state":state,"revision":r["revision"]}
 def snapshot(c,owner,r,include_timeline):
  # Hash canonical stored content, not the re-generated ZIP (ZIP timestamps vary).
  h=hashlib.sha256()
  h.update(str(r["revision"]).encode()+b"\n")
  h.update(hashlib.sha256(r["archive"]).digest())
  if include_timeline:
   row=c.execute("SELECT data FROM trip_timeline WHERE owner=? AND trip_id=?",(owner,r["id"])).fetchone()
   h.update(b"timeline\n"+hashlib.sha256(row["data"].encode()).digest() if row else b"no-timeline")
  return h.hexdigest()
 @app.get("/api/mobile/v1/trips/{tid}/offline-state")
 def offline_state(tid:str,req:Request):
  owner=auth(req)["owner"]
  with db() as c:
   r=load(c,owner,tid)
   return JSONResponse({"id":tid,"revision":r["revision"],"snapshot":snapshot(c,owner,r,True)},headers={"Cache-Control":"no-store"})
 @app.get("/api/mobile/v1/trips/{tid}/offline")
 def offline(tid:str,req:Request,include_timeline:bool=False):
  owner=auth(req)["owner"]
  with db() as c:
   r=load(c,owner,tid)
   raw=export_bundle(c,owner,r,include_timeline)
   return Response(raw,media_type="application/zip",headers={"Cache-Control":"no-store","X-NextDo-Revision":str(r["revision"]),"X-NextDo-Snapshot":snapshot(c,owner,r,include_timeline),"X-NextDo-Archive-SHA256":hashlib.sha256(raw).hexdigest()})
 @app.get("/api/mobile/v1/trips/{tid}/documents/{name}")
 def document(tid:str,name:str,req:Request):
  owner=auth(req)["owner"]
  with db() as c:
   r=load(c,owner,tid);_,_,files=read_archive(r["archive"])
   if name not in files:fail(404,"Documento non trovato")
   return Response(files[name],media_type="application/pdf",headers={"Content-Security-Policy":"sandbox"})
