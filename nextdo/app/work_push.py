"""Optional FCM HTTP v1: wake-up only, no agenda contents leave NextDo."""
import base64,hashlib,json,os,re,tempfile,threading,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from fastapi import HTTPException,Request
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from cryptography.hazmat.primitives import hashes

PACKAGE="uk.archis.nextdoviaggi"
def ensure(c):
 c.execute("""CREATE TABLE IF NOT EXISTS work_mobile_push(device_id TEXT PRIMARY KEY REFERENCES work_mobile_devices(id) ON DELETE CASCADE,token TEXT NOT NULL,project TEXT NOT NULL,signature TEXT NOT NULL DEFAULT '')""")
def path(root):return Path(root)/"work-push-private.json"
def config(root):
 try:return json.loads(path(root).read_text())
 except (OSError,ValueError):return None
def public_config(root):
 x=config(root)
 return x["android"] if x else None
def subscribe(c,did,value,project):
 c.execute("DELETE FROM work_mobile_push WHERE token=? AND device_id!=?",(value,did))
 c.execute("""INSERT INTO work_mobile_push(device_id,token,project) VALUES(?,?,?)
 ON CONFLICT(device_id) DO UPDATE SET token=excluded.token,project=excluded.project,signature=CASE WHEN token=excluded.token AND project=excluded.project THEN signature ELSE '' END""",(did,value,project))
def validated(b):
 try:
  service=b["service"];g=b["android"];project=service["project_id"];info=g["project_info"]
  if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}",project) or info["project_id"]!=project or service["type"]!="service_account":raise ValueError()
  email=service["client_email"];key=service["private_key"]
  if not isinstance(email,str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.gserviceaccount\.com",email):raise ValueError()
  if not isinstance(key,str) or len(key)>12000:raise ValueError()
  private=load_pem_private_key(key.encode(),password=None)
  if not isinstance(private,rsa.RSAPrivateKey) or private.key_size<2048:raise ValueError()
  client=next(x for x in g["client"] if x["client_info"]["android_client_info"]["package_name"]==PACKAGE)
  public={"project_id":project,"sender_id":str(info["project_number"]),"app_id":client["client_info"]["mobilesdk_app_id"],"api_key":client["api_key"][0]["current_key"]}
  if not re.fullmatch(r"\d{5,25}",public["sender_id"]) or not re.fullmatch(r"1:\d+:android:[a-f0-9]+",public["app_id"]) or not re.fullmatch(r"[A-Za-z0-9_-]{20,150}",public["api_key"]):raise ValueError()
  if public["app_id"].split(":")[1]!=public["sender_id"]:raise ValueError()
  return {"service":{"project_id":project,"client_email":email,"private_key":key},"android":public}
 except (KeyError,TypeError,ValueError,AttributeError,StopIteration,IndexError):raise HTTPException(400,"Configurazione Firebase non valida o pacchetto Android non corrispondente")
def save(root,b):
 cfg=validated(b)
 fd,tmp=tempfile.mkstemp(prefix=".work-push-",dir=root)
 try:
  with os.fdopen(fd,"w") as stream:json.dump(cfg,stream)
  os.chmod(tmp,0o600);os.replace(tmp,path(root))
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def b64(raw):return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def request(url,body,headers):
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 with opener.open(urllib.request.Request(url,data=body,headers=headers),timeout=12) as response:
  return json.loads(response.read(65536))
def oauth(service):
 now=int(time.time())
 header=b64(b'{"alg":"RS256","typ":"JWT"}')
 claims=b64(json.dumps({"iss":service["client_email"],"scope":"https://www.googleapis.com/auth/firebase.messaging","aud":"https://oauth2.googleapis.com/token","iat":now,"exp":now+3600},separators=(",",":")).encode())
 assertion=(header+"."+claims).encode()
 key=load_pem_private_key(service["private_key"].encode(),password=None)
 signed=assertion.decode()+"."+b64(key.sign(assertion,padding.PKCS1v15(),hashes.SHA256()))
 return request("https://oauth2.googleapis.com/token",urllib.parse.urlencode({"grant_type":"urn:ietf:params:oauth:grant-type:jwt-bearer","assertion":signed}).encode(),{"Content-Type":"application/x-www-form-urlencoded"})["access_token"]
def send(project,access,token):
 # Generic wake signal, no user identifiers, titles, dates or task information.
 payload={"message":{"token":token,"data":{"nextdo":"work_refresh"},"android":{"priority":"high","ttl":"120s","collapse_key":"nextdo-work"}}}
 return request("https://fcm.googleapis.com/v1/projects/"+project+"/messages:send",json.dumps(payload).encode(),{"Content-Type":"application/json","Authorization":"Bearer "+access})
def register(app,*,conn,user,csrf,accessible,data_path,revision,seen):
 def admin(req,write=False):
  u=user(req)
  if u["role"]!="admin":raise HTTPException(403,"Accesso riservato")
  if write:csrf(req)
 @app.get("/api/work-mobile/push/config")
 def status(req:Request):
  admin(req);cfg=public_config(data_path)
  return {"configured":bool(cfg),"project_id":cfg["project_id"] if cfg else None}
 @app.post("/api/work-mobile/push/config")
 def setup(req:Request,b:dict):
  admin(req,True);save(data_path,b)
  with conn() as c:ensure(c);c.execute("DELETE FROM work_mobile_push")
  return {"ok":True}
 @app.post("/api/work-mobile/push/disable")
 def disable(req:Request):
  admin(req,True);path(data_path).unlink(missing_ok=True)
  with conn() as c:ensure(c);c.execute("DELETE FROM work_mobile_push")
  return {"ok":True}
 stop=threading.Event()
 def loop():
  cached=None;access="";expiry=0
  while not stop.wait(5):
   try:
    cfg=config(data_path)
    if not cfg:continue
    project=cfg["android"]["project_id"]
    work=[]
    with conn() as c:
     ensure(c)
     devices=c.execute("""SELECT p.*,d.user_id,d.password_hash,u.password,u.role,u.active,u.username,u.display_name,u.id
     FROM work_mobile_push p JOIN work_mobile_devices d ON p.device_id=d.id
     JOIN work_mobile_alert_tokens a ON a.device_id=d.id JOIN users u ON u.id=d.user_id
     WHERE d.revoked=0 AND d.expires>? AND u.active=1 AND p.project=?""",(time.time(),project)).fetchall()
     tasks=c.execute("SELECT * FROM tasks WHERE kind IN ('task','appointment') AND status!='done' ORDER BY id").fetchall()
     for d in devices:
      if d["password_hash"]!=hashlib.sha256(d["password"].encode()).hexdigest():continue
      sig=hashlib.sha256(repr([(revision(t),seen(c,d,t) is not None) for t in tasks if accessible(c,d,t)]).encode()).hexdigest()
      if sig!=d["signature"]:work.append((d["device_id"],d["token"],sig))
    if not work:continue
    stamp=hashlib.sha256(repr(cfg["service"]).encode()).hexdigest()
    if cached!=stamp or time.time()>=expiry:
     access=oauth(cfg["service"]);cached=stamp;expiry=time.time()+3000
    for did,token,sig in work:
     if stop.is_set():return
     try:
      send(project,access,token)
      with conn() as c:c.execute("UPDATE work_mobile_push SET signature=? WHERE device_id=? AND token=? AND project=?",(sig,did,token,project))
     except urllib.error.HTTPError as e:
      if e.code==404:
       with conn() as c:c.execute("DELETE FROM work_mobile_push WHERE device_id=? AND token=?",(did,token))
      elif e.code==401:expiry=0;break
      else:break
   except Exception:
    # Credentials and provider errors must never appear in logs.
    stop.wait(25)
 @app.on_event("startup")
 def start():
  stop.clear();threading.Thread(target=loop,name="nextdo-work-push",daemon=True).start()
 @app.on_event("shutdown")
 def finish():stop.set()
