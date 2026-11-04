"""Microsoft Lists pilot: admin-only, temporary delegated read-only Microsoft Graph connection.

No password, refresh token, client secret or list content is committed to GitHub.
The delegated access token and device code stay only in process memory and expire.
All SharePoint access is GET-only. No list creation or changes happen in this phase.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

GRAPH = "https://graph.microsoft.com/v1.0"
IDENTITY = "https://login.microsoftonline.com"
SCOPE = "https://graph.microsoft.com/Sites.Read.All"
FLOWS = {}
TOKENS = {}
UUID_RE = re.compile(r"^[a-fA-F0-9-]{36}$")
HOST_RE = re.compile(r"^[a-zA-Z0-9-]+\\.sharepoint\\.com$")
SITE_PATH_RE = re.compile(r"^/(?:sites|teams)/[a-zA-Z0-9._-]+/?$")


def reject(message, code=400):
 raise HTTPException(status_code=code, detail=message)


def canonical_site(url):
 """Accept only Microsoft SharePoint site URLs (including list sharing links)."""
 parsed = urllib.parse.urlsplit(url.strip())
 host = (parsed.hostname or "").lower()
 if parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password or not HOST_RE.fullmatch(host) or host.endswith("-my.sharepoint.com"):
  reject("Inserire un collegamento HTTPS a un sito SharePoint istituzionale")
 path = urllib.parse.unquote(parsed.path)
 share = re.fullmatch(r"/:l:/s/([a-zA-Z0-9._-]+)(?:/.*)?", path, flags=re.I)
 if share:
  path = "/sites/" + share.group(1)
 path = path.rstrip("/")
 if not SITE_PATH_RE.fullmatch(path):
  reject("Inserire l'indirizzo del sito SharePoint oppure un link Microsoft Lists del sito")
 return "https://" + host + path


def validate_settings(body):
 try:
  if not UUID_RE.fullmatch(body.tenant_id.strip()):raise ValueError()
  tenant = str(uuid.UUID(body.tenant_id.strip()))
  if not UUID_RE.fullmatch(body.client_id.strip()):raise ValueError()
  client = str(uuid.UUID(body.client_id.strip()))
 except (ValueError, AttributeError):
  reject("ID tenant e ID applicazione devono essere identificativi Microsoft (GUID)")
 return {"tenant_id":tenant,"client_id":client,"site_url":canonical_site(body.site_url),"list_id":"","list_name":""}


def _settings_file(data):
 return Path(data) / "microsoft-lists-pilot.json"


def read_settings(data):
 path = _settings_file(data)
 if not path.is_file():
  return {}
 try:
  value = json.loads(path.read_text(encoding="utf-8"))
  return value if isinstance(value,dict) else {}
 except (ValueError,OSError):
  return {}


def save_settings(data,config):
 path = _settings_file(data)
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp = path.parent / ("." + path.name + "-" + secrets.token_hex(8))
 try:
  fd = os.open(tmp, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
  with os.fdopen(fd,"w",encoding="utf-8") as out:
   json.dump(config,out,ensure_ascii=False)
  os.replace(tmp,path)
 finally:
  if tmp.exists():tmp.unlink()


def _http_json(url, form=None, token=None):
 """Only two fixed Microsoft origins are allowed to receive our requests."""
 target=urllib.parse.urlsplit(url)
 if target.scheme!="https" or target.netloc not in ("graph.microsoft.com","login.microsoftonline.com"):
  raise ValueError("Endpoint Microsoft non consentito")
 headers={"Accept":"application/json"}
 if token:headers["Authorization"]="Bearer "+token
 data=None
 if form is not None:
  data=urllib.parse.urlencode(form).encode("utf-8")
  headers["Content-Type"]="application/x-www-form-urlencoded"
 request=urllib.request.Request(url,data=data,headers=headers,method="POST" if form is not None else "GET")
 try:
  with urllib.request.urlopen(request,timeout=15) as response:
   return response.status,json.loads(response.read(2_000_000).decode("utf-8"))
 except urllib.error.HTTPError as error:
  try: payload=json.loads(error.read(16_384).decode("utf-8"))
  except (ValueError,UnicodeError):payload={}
  return error.code,payload


def _graph(path,token):
 url=path if path.startswith("https://") else GRAPH+path
 parsed=urllib.parse.urlsplit(url)
 if parsed.scheme!="https" or parsed.netloc!="graph.microsoft.com" or not parsed.path.startswith("/v1.0/"):
  reject("Richiesta Graph non consentita",400)
 status,data=_http_json(url,token=token)
 if status>=400:
  code=data.get("error",{}).get("code","") if isinstance(data,dict) else ""
  if status in (401,403):reject("Microsoft 365 ha rifiutato l'accesso ("+str(code)[:64]+"). Verificare autorizzazioni dell'app.",403)
  reject("Lettura da Microsoft Graph non riuscita ("+str(status)+", "+str(code)[:64]+")",502)
 return data


def _all_graph(path,token,max_pages=8):
 items=[]
 for _ in range(max_pages):
  page=_graph(path,token)
  items.extend(page.get("value",[]))
  path=page.get("@odata.nextLink")
  if not path:return items
 reject("L'elenco ha troppe pagine: interrompo la lettura senza modificarlo",413)


def _site_details(config,token):
 parsed=urllib.parse.urlsplit(config["site_url"])
 site=_graph("/sites/"+parsed.netloc+":"+urllib.parse.quote(parsed.path,safe="/"),token)
 if "id" not in site:reject("Sito SharePoint non riconosciuto da Microsoft Graph",502)
 return site


def register_routes(app, *, user, csrf, data_path):
 def admin(req):
  current=user(req)
  if current["role"]!="admin":reject("Funzione riservata agli amministratori NextDo",403)
  return current

 def active_token(uid):
  token=TOKENS.get(uid)
  if not token or token["until"]<=time.monotonic()+20:
   TOKENS.pop(uid,None)
   reject("Sessione Microsoft assente o scaduta. Collega nuovamente l'account.",401)
  return token["token"]

 class Config(BaseModel):
  tenant_id:str=Field(min_length=1,max_length=80)
  client_id:str=Field(min_length=1,max_length=80)
  site_url:str=Field(min_length=1,max_length=1024)

 class SelectList(BaseModel):
  list_id:str=Field(min_length=1,max_length=128)

 @app.get("/api/microsoft/config")
 def current_config(req:Request):
  u=admin(req)
  config=read_settings(data_path)
  token=TOKENS.get(u["id"])
  return {**config,"authenticated":bool(token and token["until"]>time.monotonic()+20),
    "mode":"read_only_pilot","uses_saved_tokens":False}

 @app.post("/api/microsoft/config")
 def set_config(b:Config,req:Request):
  u=admin(req);csrf(req)
  validated=validate_settings(b)
  save_settings(data_path,validated)
  TOKENS.pop(u["id"],None);FLOWS.pop(u["id"],None)
  return {"ok":True,"site_url":validated["site_url"],"mode":"read_only_pilot"}

 @app.post("/api/microsoft/auth/start")
 def auth_start(req:Request):
  u=admin(req);csrf(req)
  config=read_settings(data_path)
  if not all(config.get(k) for k in ("tenant_id","client_id","site_url")):
   reject("Configurare prima tenant, ID applicazione e sito SharePoint")
  # Do not ask for persistent offline_access: this is a short read-only pilot.
  url=IDENTITY+"/"+config["tenant_id"]+"/oauth2/v2.0/devicecode"
  status,result=_http_json(url,form={"client_id":config["client_id"],"scope":SCOPE})
  if status>=400 or "device_code" not in result:
   reject("Microsoft non ha avviato l'accesso. Verificare che l'app Entra sia registrata come client pubblico.",400)
  FLOWS[u["id"]]={"device_code":result["device_code"],"tenant":config["tenant_id"],
   "client_id":config["client_id"],"expires":time.monotonic()+min(int(result.get("expires_in",900)),1200),
   "interval":max(int(result.get("interval",5)),5),"next_check":0}
  return {"user_code":result["user_code"],"verification_uri":result["verification_uri"],
   "expires_in":result.get("expires_in",900),"interval":FLOWS[u["id"]]["interval"]}

 @app.post("/api/microsoft/auth/check")
 def auth_check(req:Request):
  u=admin(req);csrf(req)
  flow=FLOWS.get(u["id"])
  if not flow or flow["expires"]<time.monotonic():
   FLOWS.pop(u["id"],None)
   reject("Codice Microsoft scaduto: ripetere il collegamento",400)
  if flow["next_check"]>time.monotonic():
   return {"status":"pending","retry_after":max(1,round(flow["next_check"]-time.monotonic()))}
  flow["next_check"]=time.monotonic()+flow["interval"]
  url=IDENTITY+"/"+flow["tenant"]+"/oauth2/v2.0/token"
  status,reply=_http_json(url,form={"grant_type":"urn:ietf:params:oauth:grant-type:device_code",
    "client_id":flow["client_id"],"device_code":flow["device_code"]})
  if status>=400:
   error=reply.get("error","") if isinstance(reply,dict) else ""
   if error in ("authorization_pending","slow_down"):
    if error=="slow_down":flow["interval"]+=5
    return {"status":"pending","retry_after":flow["interval"]}
   FLOWS.pop(u["id"],None)
   if error in ("authorization_declined","access_denied","consent_required"):
    reject("Accesso negato o consenso non disponibile. Potrebbe essere necessaria l'approvazione Microsoft 365 dell'Ateneo.",403)
   reject("Collegamento Microsoft non completato ("+str(error)[:64]+")",400)
  if "access_token" not in reply:reject("Microsoft non ha restituito un token valido",502)
  TOKENS[u["id"]]={"token":reply["access_token"],"until":time.monotonic()+min(int(reply.get("expires_in",3600)),3600)}
  FLOWS.pop(u["id"],None)
  return {"status":"connected","temporary":True}

 @app.post("/api/microsoft/auth/disconnect")
 def auth_disconnect(req:Request):
  u=admin(req);csrf(req)
  TOKENS.pop(u["id"],None);FLOWS.pop(u["id"],None)
  return {"ok":True}

 @app.get("/api/microsoft/lists")
 def list_lists(req:Request):
  u=admin(req)
  config=read_settings(data_path)
  if not config.get("site_url"):reject("Configurazione Microsoft mancante")
  token=active_token(u["id"])
  site=_site_details(config,token)
  lists=_all_graph("/sites/"+urllib.parse.quote(site["id"],safe=",")+"/lists?$select=id,displayName,webUrl,list",token)
  return {"site":{"id":site["id"],"name":site.get("displayName",""),"url":site.get("webUrl","")},
    "lists":[{"id":x["id"],"name":x.get("displayName",""),"url":x.get("webUrl","")}
    for x in lists if x.get("id") and x.get("list") is not None]}

 @app.post("/api/microsoft/list/select")
 def choose_list(b:SelectList,req:Request):
  u=admin(req);csrf(req)
  config=read_settings(data_path)
  token=active_token(u["id"])
  site=_site_details(config,token)
  lists=_all_graph("/sites/"+urllib.parse.quote(site["id"],safe=",")+"/lists?$select=id,displayName,webUrl,list",token)
  target=next((x for x in lists if x.get("id")==b.list_id and x.get("list") is not None),None)
  if not target:reject("Selezionare un elenco effettivamente presente nel sito SharePoint",404)
  config.update({"list_id":target["id"],"list_name":target.get("displayName","")})
  save_settings(data_path,config)
  return {"ok":True,"list_name":config["list_name"]}

 @app.get("/api/microsoft/list/inspect")
 def inspect_list(req:Request):
  u=admin(req)
  config=read_settings(data_path)
  if not config.get("list_id"):reject("Selezionare prima un elenco")
  token=active_token(u["id"])
  site=_site_details(config,token)
  base="/sites/"+urllib.parse.quote(site["id"],safe=",")+"/lists/"+urllib.parse.quote(config["list_id"],safe="")
  columns=_all_graph(base+"/columns?$select=name,displayName",token)
  names={c.get("name") for c in columns}
  return {"list_name":config.get("list_name",""),"column_names":sorted(x for x in names if isinstance(x,str)),
    "needed_for_sync":["NextDoID","NextDoProject","NextDoStatus","NextDoNote"],
    "ready_for_sync":all(x in names for x in ("NextDoID","NextDoProject","NextDoStatus","NextDoNote")),
    "read_only":True,"message":"Verifica completata in sola lettura. Nessuna colonna o attività è stata modificata."}
