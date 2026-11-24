"""Private travel archive. No personal contents in source control or work APIs."""
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit
import hashlib, io, json, os, re, secrets, sqlite3, threading, time, zipfile
from fastapi import HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from argon2.exceptions import VerificationError
from . import personal_travel_tools as tools
from . import travel_mobile

LIMIT=32*1024*1024
MAX_EXPANDED=120*1024*1024
ID=re.compile(r"^[a-z0-9][a-z0-9_-]{1,47}$")
NAME=re.compile(r"^[a-zA-Z0-9À-ÿ][a-zA-Z0-9À-ÿ_.() -]{0,110}\.pdf$",re.I)
def fail(msg,status=400):
 raise HTTPException(status_code=status,detail=msg)

def dump(obj):
 return json.dumps(obj,ensure_ascii=False,separators=(",",":"))

def parse_date(v):
 if not isinstance(v,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",v):fail("Data non valida")
 try:return date.fromisoformat(v)
 except ValueError:fail("Data non valida")

def validate_shape(v,depth=0):
 if depth>10:fail("Manifest troppo complesso")
 if isinstance(v,str):
  if len(v)>20000 or "\x00" in v:fail("Testo non valido")
 elif isinstance(v,list):
  if len(v)>200:fail("Troppe voci")
  for a in v:validate_shape(a,depth+1)
 elif isinstance(v,dict):
  if len(v)>200:fail("Troppe proprietà")
  for k,a in v.items():validate_shape(k,depth+1);validate_shape(a,depth+1)
 elif v is not None and not isinstance(v,(bool,int,float)):fail("Valore non valido")

def validate_manifest(m,available):
 if isinstance(m,dict):
  tools.validate_cover(m.get('cover'))
  validate_shape({k:v for k,v in m.items() if k not in ('cover','travel_photos')})
  photos=m.get('travel_photos',{})
  if not isinstance(photos,dict) or len(photos)>80:fail('Troppe foto del viaggio')
  total=0
  for key,img in photos.items():
   if not isinstance(key,str) or not re.fullmatch(r'(?:day|booking):[a-z0-9_-]{2,48}',key) or img is None:fail('Foto del viaggio non valida')
   tools.validate_cover(img);total+=len(img['jpeg'])
  if total>12_000_000:fail('Limite immagini del viaggio raggiunto')
 else:validate_shape(m)
 if not isinstance(m,dict) or m.get("format_version")!=1:fail("Richiesto manifest.json formato 1")
 t=m.get("trip")
 if not isinstance(t,dict) or not ID.fullmatch(str(t.get("id",""))) or not isinstance(t.get("title"),str) or not t["title"].strip():fail("Viaggio non valido")
 start,end=parse_date(t.get("start")),parse_date(t.get("end"))
 if not 0<=(end-start).days<180:fail("Periodo non valido (massimo 180 giorni)")
 refs=set()
 def doc(name):
  if name:
   if not isinstance(name,str) or not NAME.fullmatch(name):fail("Nome PDF non valido")
   refs.add(name)
 def rows(key,maximum):
  a=m.get(key,[])
  if not isinstance(a,list) or len(a)>maximum or any(not isinstance(x,dict) for x in a):fail("Sezione non valida: "+key)
  return a
 def ids(a):
  result=set()
  for x in a:
   ident=x.get("id")
   if not isinstance(ident,str) or not ID.fullmatch(ident) or ident in result:fail("Identificativo non valido o duplicato")
   result.add(ident)
  return result
 def pairs(a):
  if not isinstance(a,list) or any(not isinstance(x,list) or len(x)!=2 or any(not isinstance(y,str) for y in x) for x in a):fail("Dettagli non validi")
 def link(v):
  if not v:return
  if not isinstance(v,str) or any(ord(c)<32 for c in v):fail("Link non valido")
  try:p=urlsplit(v)
  except ValueError:fail("Link non valido")
  if p.scheme!="https" or not p.hostname or p.username or p.password:fail("Sono ammessi soltanto link HTTPS")
 def locations(items):
  if not isinstance(items,list) or len(items)>30 or any(not isinstance(x,dict) for x in items):fail("Elenco luoghi non valido")
  ids(items)
  for loc in items:
   if not isinstance(loc.get("label"),str) or not loc["label"].strip():fail("Nome luogo obbligatorio")
   for field in ("role","address","code","time","notes"):
    if field in loc and not isinstance(loc[field],str):fail("Campo luogo non valido")
   if loc.get("lat") is not None or loc.get("lon") is not None:tools.coordinates(loc.get("lat"),loc.get("lon"))
   link(loc.get("map"))
 bookings=rows("bookings",160);bids=ids(bookings)
 for b in bookings:
  doc(b.get("doc"));pairs(b.get("lines",[]))
  locations(b.get("locations",[]));pairs(b.get("fields",[]))
  for key in ("source","map","extraLink"):link(b.get(key))
 guides=rows("guides",50);gids=ids(guides)
 for g in guides:
  doc(g.get("doc"));pairs(g.get("items",[]))
  links=g.get("links",[])
  if not isinstance(links,list) or any(not isinstance(x,dict) for x in links):fail("Link guida non validi")
  for x in links:link(x.get("url"))
 seen=set()
 for d in rows("days",180):
  dt=parse_date(d.get("date"))
  if dt in seen or not start<=dt<=end:fail("Giornata duplicata o fuori periodo")
  seen.add(dt)
  locations(d.get("route_points",[]))
  if d.get("route_mode","drive") not in ("drive","walk","bicycle"):fail("Modalità percorso non valida")
  events=d.get("events",[]);checks=d.get("checks",[])
  if not isinstance(events,list) or not isinstance(checks,list) or len(events)>100 or len(checks)>100 or any(not isinstance(x,str) for x in checks):fail("Eventi o checklist non validi")
  for e in events:
   if not isinstance(e,dict) or (e.get("bid") and e["bid"] not in bids) or (e.get("gid") and e["gid"] not in gids):fail("Collegamento evento non valido")
 for d in rows("documents",160):doc(d.get("file"))
 for e in rows("expenses",160):
  if not isinstance(e.get("title"),str) or not e["title"].strip():fail("Spesa non valida")
  tools.validate_expense(e)
  doc(e.get("doc"))
 if any(k not in {"day:"+d["date"] for d in m.get("days",[])}|{"booking:"+i for i in bids} for k in m.get("travel_photos",{})):fail("Foto associata a una tappa inesistente")
 if refs!=set(available):fail("PDF mancanti o non dichiarati")
 return m

def validate_state(state,m):
 validate_shape(state)
 if not isinstance(state,dict) or not isinstance(state.get("notes"),dict) or not isinstance(state.get("checks"),dict):fail("Note o checklist non valide")
 days={d["date"]:d for d in m.get("days",[])}
 for d,n in state["notes"].items():
  if d not in days or not isinstance(n,str):fail("Nota non valida")
 for d,vals in state["checks"].items():
  if d not in days or not isinstance(vals,list) or any(type(i)!=int or not 0<=i<len(days[d].get("checks",[])) for i in vals):fail("Checklist non valida")
 return {"notes":state["notes"],"checks":state["checks"]}

def read_archive(raw):
 if len(raw)>LIMIT:fail("Archivio oltre 32 MB",413)
 try:
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   entries=z.infolist()
   if len(entries)>180 or sum(i.file_size for i in entries)>MAX_EXPANDED:fail("Archivio troppo grande",413)
   data={}
   for i in entries:
    if i.is_dir():continue
    name=i.filename
    if i.flag_bits&1 or (i.external_attr>>16)&0o170000==0o120000 or name in data:fail("Elemento ZIP non ammesso")
    if name not in ("manifest.json","notes.json") and not(name.startswith("documenti/") and NAME.fullmatch(name[10:])):fail("Percorso ZIP non ammesso")
    if i.file_size>LIMIT or (i.file_size>1024*1024 and i.file_size>250*max(1,i.compress_size)):fail("Compressione o dimensione anomala",413)
    data[name]=z.read(i)
  m=json.loads(data.pop("manifest.json"))
  state=json.loads(data.pop("notes.json",b'{"notes":{},"checks":{}}'))
  files={k[10:]:v for k,v in data.items()}
  if any(not v.startswith(b"%PDF-") for v in files.values()):fail("Documento non PDF")
  validate_manifest(m,files)
  return m,validate_state(state,m),files
 except (zipfile.BadZipFile,KeyError,ValueError,UnicodeError,RuntimeError,NotImplementedError,TypeError,RecursionError):fail("Archivio ZIP o manifest non valido")

def make_archive(m,state,files):
 out=io.BytesIO()
 with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
  z.writestr("manifest.json",dump(m))
  z.writestr("notes.json",dump({"revision":0,**state}))
  for name,pdf in files.items():z.writestr("documenti/"+name,pdf)
 raw=out.getvalue()
 if len(raw)>LIMIT:fail("Archivio oltre 32 MB",413)
 return raw

def new_manifest(b):
 start,end=parse_date(b.get("start")),parse_date(b.get("end"))
 if not 0<=(end-start).days<180:fail("Periodo non valido (massimo 180 giorni)")
 tid="trip-"+secrets.token_hex(8)
 m={"format_version":1,"trip":{"id":tid,"title":b.get("title"),"subtitle":b.get("subtitle",""),"start":start.isoformat(),"end":end.isoformat()},"bookings":[],"documents":[],"guides":[],"days":[{"date":(start+timedelta(days=i)).isoformat(),"place":"","headline":"","description":"","events":[],"checks":[]} for i in range((end-start).days+1)]}
 return m

def register_routes(app,*,user,csrf,conn,data_path,ph):
 root=Path(data_path)/"personal";root.mkdir(mode=0o700,exist_ok=True)
 database=root/"trips.sqlite3"
 mutex=threading.RLock()
 grants={}
 @contextmanager
 def db():
  with mutex:
   c=sqlite3.connect(database,timeout=20);c.row_factory=sqlite3.Row
   try:
    yield c
    c.commit()
   except BaseException:c.rollback();raise
   finally:c.close()
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS pins(owner TEXT PRIMARY KEY,pin TEXT NOT NULL,attempts INTEGER DEFAULT 0,blocked_until REAL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS trips(owner TEXT NOT NULL,id TEXT NOT NULL,archive BLOB NOT NULL,title TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,revision INTEGER DEFAULT 0,PRIMARY KEY(owner,id));""")
 with db() as c:c.execute("CREATE TABLE IF NOT EXISTS travel_services(owner TEXT NOT NULL,name TEXT NOT NULL,secret TEXT NOT NULL,PRIMARY KEY(owner,name))")
 os.chmod(database,0o600)
 # Stable account binding; deleting an account cascades its identity, so reused IDs cannot read old trips.
 with conn() as c:
  c.execute("CREATE TABLE IF NOT EXISTS personal_identities(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,owner TEXT UNIQUE NOT NULL)")
 def identity(req):
  u=user(req)
  with conn() as c:
   c.execute("CREATE TABLE IF NOT EXISTS personal_identities(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,owner TEXT UNIQUE NOT NULL)")
   c.execute("INSERT OR IGNORE INTO personal_identities(user_id,owner) VALUES(?,?)",(u["id"],secrets.token_hex(32)))
   owner=c.execute("SELECT owner FROM personal_identities WHERE user_id=?",(u["id"],)).fetchone()[0]
  session=hashlib.sha256(req.cookies["nextdo_session"].encode()).hexdigest()
  return owner,session
 def allowed(req,write=False):
  owner,session=identity(req)
  if write:csrf(req)
  with mutex:
   now=time.monotonic()
   for k,v in list(grants.items()):
    if v<=now:grants.pop(k,None)
   if (owner,session) not in grants:fail("Area personale bloccata",423)
   grants[(owner,session)]=now+300
  return owner
 def grant(owner,session):
  with mutex:grants[(owner,session)]=time.monotonic()+300
 def load(c,owner,tid):
  r=c.execute("SELECT * FROM trips WHERE owner=? AND id=?",(owner,tid)).fetchone()
  if r is None:fail("Viaggio non trovato",404)
  return r
 def save(c,owner,m,state,files,revision=None):
  validate_manifest(m,files);state=validate_state(state,m)
  archive=make_archive(m,state,files)
  t=m["trip"]
  if revision is None:
   if c.execute("SELECT 1 FROM trips WHERE owner=? AND id=?",(owner,t["id"])).fetchone():fail("Viaggio già presente: nessuna sovrascrittura automatica",409)
   c.execute("INSERT INTO trips(owner,id,archive,title,start,end) VALUES(?,?,?,?,?,?)",(owner,t["id"],archive,t["title"],t["start"],t["end"]))
   return 0
  cur=c.execute("UPDATE trips SET archive=?,title=?,start=?,end=?,revision=revision+1 WHERE owner=? AND id=? AND revision=?",(archive,t["title"],t["start"],t["end"],owner,t["id"],revision))
  if not cur.rowcount:fail("Il viaggio è stato modificato: ricaricare",409)
  return revision+1
 travel_mobile.register(app,db=db,mutex=mutex,conn=conn,allowed=allowed,ph=ph,load=load,read_archive=read_archive,save=save,new_manifest=new_manifest,limit=LIMIT)
 @app.middleware("http")
 async def private_cache(req:Request,call_next):
  res=await call_next(req)
  if req.url.path.startswith(("/api/personal/","/api/mobile/v1/")):
   res.headers["Cache-Control"]="no-store, private"
   res.headers["Referrer-Policy"]="no-referrer"
   res.headers["X-Content-Type-Options"]="nosniff"
  return res
 @app.get("/api/personal/status")
 def status(req:Request):
  owner,session=identity(req)
  with db() as c:configured=bool(c.execute("SELECT 1 FROM pins WHERE owner=?",(owner,)).fetchone())
  with mutex:unlocked=grants.get((owner,session),0)>time.monotonic()
  return {"configured":configured,"unlocked":unlocked}
 @app.post("/api/personal/unlock")
 def unlock(req:Request,b:dict):
  owner,session=identity(req);csrf(req)
  pin=b.get("pin")
  if not isinstance(pin,str) or not re.fullmatch(r"[0-9]{6}",pin):fail("Inserire un PIN di 6 cifre")
  error=None
  with db() as c:
   r=c.execute("SELECT * FROM pins WHERE owner=?",(owner,)).fetchone()
   if r is None:
    if b.get("confirm")!=pin:fail("Confermare il PIN")
    c.execute("INSERT INTO pins(owner,pin) VALUES(?,?)",(owner,ph.hash(pin)))
   elif r["blocked_until"]>time.time():error=("Troppi tentativi. Riprovare tra 5 minuti",429)
   else:
    try:ok=ph.verify(r["pin"],pin)
    except VerificationError:ok=False
    if not ok:
     n=r["attempts"]+1
     c.execute("UPDATE pins SET attempts=?,blocked_until=? WHERE owner=?",(0 if n>=5 else n,time.time()+300 if n>=5 else 0,owner))
     error=("PIN non corretto",403)
    else:c.execute("UPDATE pins SET attempts=0,blocked_until=0 WHERE owner=?",(owner,))
  if error:fail(*error)
  grant(owner,session)
  return {"unlocked":True}
 @app.post("/api/personal/lock")
 def lock(req:Request):
  owner,session=identity(req);csrf(req)
  with mutex:grants.pop((owner,session),None)
  return {"ok":True}
 @app.get("/api/personal/trips")
 def list_trips(req:Request):
  owner=allowed(req)
  with db() as c:return [dict(x) for x in c.execute("SELECT id,title,start,end FROM trips WHERE owner=? ORDER BY start DESC",(owner,))]
 @app.post("/api/personal/trips/import")
 def import_trip(req:Request,file:UploadFile=File(...)):
  owner=allowed(req,True)
  m,state,files=read_archive(file.file.read(LIMIT+1))
  with db() as c:save(c,owner,m,state,files)
  return {"id":m["trip"]["id"],"bookings":len(m.get("bookings",[])),"days":len(m.get("days",[])),"guides":len(m.get("guides",[])),"pdfs":len(files)}
 @app.post("/api/personal/trips")
 def new_trip(req:Request,b:dict):
  owner=allowed(req,True)
  m=new_manifest(b);tid=m["trip"]["id"]
  with db() as c:save(c,owner,m,{"notes":{},"checks":{}},{})
  return {"id":tid}
 @app.get("/api/personal/trips/{tid}")
 def get_trip(tid:str,req:Request):
  owner=allowed(req)
  with db() as c:
   r=load(c,owner,tid);m,state,files=read_archive(r["archive"])
   return {"manifest":m,"state":state,"revision":r["revision"]}
 @app.put("/api/personal/trips/{tid}")
 def update_trip(tid:str,req:Request,b:dict):
  owner=allowed(req,True)
  m=b.get("manifest");state=b.get("state");rev=b.get("revision")
  if not isinstance(m,dict) or not isinstance(m.get("trip"),dict) or m["trip"].get("id")!=tid or type(rev)!=int:fail("Modifica non valida")
  with db() as c:
   r=load(c,owner,tid);_,_,files=read_archive(r["archive"])
   return {"revision":save(c,owner,m,state,files,rev)}
 @app.post("/api/personal/trips/{tid}/documents")
 def upload_doc(tid:str,req:Request,file:UploadFile=File(...)):
  owner=allowed(req,True)
  name=file.filename or ""
  raw=file.file.read(LIMIT+1)
  if not NAME.fullmatch(name) or len(raw)>LIMIT or not raw.startswith(b"%PDF-"):fail("Caricare un PDF valido (massimo 32 MB)")
  with db() as c:
   r=load(c,owner,tid);m,state,files=read_archive(r["archive"])
   if name in files:fail("Documento già presente",409)
   files[name]=raw;m.setdefault("documents",[]).append({"file":name,"title":name})
   return {"revision":save(c,owner,m,state,files,r["revision"])}
 @app.get("/api/personal/trips/{tid}/documents/{name}")
 def download_doc(tid:str,name:str,req:Request):
  owner=allowed(req)
  with db() as c:
   r=load(c,owner,tid);_,_,files=read_archive(r["archive"])
   if name not in files:fail("Documento non trovato",404)
   from urllib.parse import quote
   return Response(files[name],media_type="application/pdf",headers={"Content-Disposition":"inline; filename*=UTF-8''"+quote(name,safe=""),"Content-Security-Policy":"sandbox"})
 @app.post("/api/personal/trips/{tid}/cover")
 def cover(tid:str,req:Request,file:UploadFile=File(...)):
  owner=allowed(req,True)
  image=tools.photo(file.file.read(5*1024*1024+1))
  with db() as c:
   r=load(c,owner,tid);m,state,files=read_archive(r["archive"])
   m["cover"]=image
   return {"revision":save(c,owner,m,state,files,r["revision"])}
 def service(owner,name):
  with db() as c:r=c.execute("SELECT secret FROM travel_services WHERE owner=? AND name=?",(owner,name)).fetchone()
  if not r:return ""
  try:return tools.email_intake._cipher(data_path).decrypt(r["secret"].encode()).decode()
  except Exception:fail("Chiave del servizio non leggibile",500)
 @app.get("/api/personal/services")
 def services(req:Request):
  owner=allowed(req)
  with db() as c:names={r[0] for r in c.execute("SELECT name FROM travel_services WHERE owner=?",(owner,))}
  return {"geoapify_configured":"geoapify" in names}
 @app.post("/api/personal/services")
 def save_services(req:Request,b:dict):
  owner=allowed(req,True)
  updates={}
  for name in ("geoapify",):
   key=b.get(name)
   if key is None or key=="":continue
   updates[name]=tools.email_intake._cipher(data_path).encrypt(tools.service_key(key.strip() if isinstance(key,str) else key).encode()).decode()
  remove=b.get("remove",[])
  if not isinstance(remove,list) or any(x not in ("geoapify",) for x in remove):fail("Servizio non valido")
  with db() as c:
   for name,value in updates.items():c.execute("INSERT OR REPLACE INTO travel_services(owner,name,secret) VALUES(?,?,?)",(owner,name,value))
   for name in remove:c.execute("DELETE FROM travel_services WHERE owner=? AND name=?",(owner,name))
  return {"ok":True}
 def assign_photo(m,target,image):
  if target=="cover":m["cover"]=image;return
  if target not in {"day:"+d["date"] for d in m.get("days",[])}|{"booking:"+b["id"] for b in m.get("bookings",[])}:fail("Tappa non trovata")
  m.setdefault("travel_photos",{})[target]=image
 @app.post("/api/personal/trips/{tid}/photo/upload")
 def upload_photo(tid:str,req:Request,target:str="cover",file:UploadFile=File(...)):
  owner=allowed(req,True);image=tools.photo(file.file.read(5*1024*1024+1))
  with db() as c:
   r=load(c,owner,tid);m,state,files=read_archive(r["archive"])
   assign_photo(m,target,image)
   return {"revision":save(c,owner,m,state,files,r["revision"])}
 @app.post("/api/personal/geocode")
 def geocode(req:Request,b:dict):
  owner=allowed(req,True)
  key=service(owner,"geoapify") or b.get("key")
  if not key:fail("Configura la chiave Geoapify in Servizi Viaggi")
  return tools.geocode(b.get("query"),key)
 @app.post("/api/personal/trips/{tid}/route")
 def calculate_route(tid:str,req:Request,b:dict):
  owner=allowed(req,True)
  with db() as c:
   r=load(c,owner,tid);m,_,_=read_archive(r["archive"])
   day=next((d for d in m.get("days",[]) if d["date"]==b.get("date")),None)
   if day is None:fail("Giornata non trovata",404)
   points=day.get("route_points",[])
   mode=day.get("route_mode","drive")
  key=service(owner,"geoapify")
  if not key:fail("Configura la chiave Geoapify in Servizi Viaggi")
  return tools.route(points,mode,key)
 @app.get("/api/personal/trips/{tid}/documents/{name}/text")
 def pdf_text(tid:str,name:str,req:Request):
  owner=allowed(req)
  with db() as c:
   r=load(c,owner,tid);_,_,files=read_archive(r["archive"])
   if name not in files:fail("Documento non trovato",404)
   raw=files[name]
  return {"text":tools.pdf_text(raw)}
 @app.post("/api/personal/analyze-booking")
 def analyze_booking(req:Request,b:dict):
  allowed(req,True)
  if user(req)["role"]!="admin":fail("Analisi AI disponibile all'amministratore",403)
  return tools.analyze_booking(data_path,b.get("text"))
 @app.get("/api/personal/trips/{tid}/export")
 def export_trip(tid:str,req:Request):
  owner=allowed(req)
  with db() as c:
   r=load(c,owner,tid)
   return Response(r["archive"],media_type="application/zip",headers={"Content-Disposition":'attachment; filename="viaggio_'+tid+'.zip"'})
