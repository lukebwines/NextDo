"""Interactive, private Airportia MCP lookup. No scheduler, no persistent flight-data store."""
from datetime import datetime, date, timezone
import json
import re
import threading
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from fastapi import HTTPException, Request as APIRequest

URL = "https://www.airportia.com/mcp"
UTC = timezone.utc

def code(value):
 return "".join(value.upper().split()) if isinstance(value,str) else ""

def obj(value):
 return value if isinstance(value,dict) else {}

def stamp(value):
 try:
  result=datetime.fromisoformat(value.replace("Z","+00:00"))
  return result if result.utcoffset() is not None else None
 except (AttributeError,TypeError,ValueError,OverflowError):return None

def local_day(value):
 if not isinstance(value,str):return None
 try:
  if re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):return date.fromisoformat(value).isoformat()
  if re.fullmatch(r"\d{2}/\d{2}/\d{4}",value):return datetime.strptime(value,"%d/%m/%Y").date().isoformat()
 except ValueError:pass
 return None

def identity(b):
 kind=b.get("kind")
 if kind!="flight" and (kind or not re.fullmatch(r"volo|voli|flight|volo aereo",str(b.get("type","")).strip(),re.I)):
  return None
 pairs=[p for k in ("fields","lines") for p in b.get(k,[]) if isinstance(p,list) and len(p)==2 and all(isinstance(x,str) for x in p)]
 def fields(labels):
  return [v.strip() for k,v in pairs if k.strip().casefold() in labels and v.strip()]
 def one(values,fn,pattern):
  normalized=[fn(v) for v in values]
  return normalized[0] if normalized and all(v and re.fullmatch(pattern,v) and v==normalized[0] for v in normalized) else None
 def airports(role,labels):
  return fields(labels)+[x["code"] for x in b.get("locations",[]) if isinstance(x,dict) and str(x.get("role","")).casefold()==role and isinstance(x.get("code"),str) and x["code"].strip()]
 number=one(fields({"numero volo","flight number"}),code,r"[A-Z0-9]{2}[0-9]{1,4}[A-Z]?")
 origin=one(airports("partenza",{"aeroporto partenza (iata)","aeroporto partenza","aeroporto di partenza","departure airport"}),code,r"[A-Z]{3}")
 dest=one(airports("arrivo",{"aeroporto arrivo (iata)","aeroporto arrivo","aeroporto di arrivo","arrival airport"}),code,r"[A-Z]{3}")
 day=one(fields({"data partenza","data di partenza","departure date"}) or [b.get("date","")],local_day,r"\d{4}-\d{2}-\d{2}")
 return (number,day,origin,dest) if all((number,day,origin,dest)) and origin!=dest else None

def matches(f,case):
 f=obj(f);number,day,origin,dest=case
 aliases=f.get("code_shares")
 numbers=[f.get("number")]+(aliases if isinstance(aliases,list) else [])
 scheduled=stamp(obj(f.get("departure")).get("scheduled"))
 # Airportia documents local timestamps with offset; never convert to server timezone.
 return (number in map(code,numbers) and obj(f.get("from")).get("iata")==origin
         and obj(f.get("to")).get("iata")==dest and scheduled is not None
         and scheduled.date().isoformat()==day)

def leg(raw):
 raw=obj(raw)
 times={k:stamp(raw.get(k)) for k in ("scheduled","estimated","actual")}
 basis=next((k for k in ("actual","estimated","scheduled") if times[k]),None)
 delta=(times[basis].astimezone(UTC)-times["scheduled"].astimezone(UTC)).total_seconds()/60 if basis in ("actual","estimated") and times["scheduled"] else None
 def short(v):return v[:40] if isinstance(v,str) else None
 return {**{k:v.isoformat() if v else None for k,v in times.items()},"basis":basis,"delta_minutes":delta,"gate":short(raw.get("gate")),"terminal":short(raw.get("terminal"))}

def normalize(f,now):
 dep,arr=(leg(f.get(k)) for k in ("departure","arrival"))
 status=f.get("status")
 status=status.strip().casefold() if isinstance(status,str) else ""
 cancelled=bool(re.fullmatch(r"cancelled|canceled",status))
 conflict=(arr["actual"] and ("en-route" in status or "scheduled" in status or cancelled)
           or dep["actual"] and ("scheduled" in status or cancelled)
           or any(x["actual"] and stamp(x["actual"])>now for x in (dep,arr))
           or dep["actual"] and arr["actual"] and stamp(dep["actual"])>stamp(arr["actual"])
           or "landed" in status and not arr["actual"] or "diverted" in status)
 if conflict:return None
 def label(x,arrival=False):
  phase="Arrivo" if arrival else "Partenza"
  d=x["delta_minutes"]
  if x["basis"]=="actual":
   prefix="Arrivato" if arrival else "Partito"
  elif x["basis"]=="estimated":
   prefix=phase+" stimata" if not arrival else "Arrivo stimato"
  else:return phase+" programmata" if not arrival else "Arrivo programmato"
  if d is None:return prefix+" · puntualità non verificabile"
  if d>0:return prefix+" · ritardo "+format(d,"g")+" min"
  if d<0:return prefix+" · anticipo "+format(-d,"g")+" min"
  return prefix+" in orario"
 return {"state":"Cancellato" if cancelled else label(dep),"departure":dep,"arrival":arr,
         "arrival_state":None if cancelled else label(arr),"cancelled":cancelled}

def evaluate(case,call,now=None):
 for name,args in (("flight_status",{"flight_number":case[0],"date":case[1]}),("airport_board",{"airport":case[2],"direction":"departures"})):
  reply=obj(call(name,args))
  rows=obj(reply.get("structuredContent")).get("flights")
  selected=[f for f in rows if isinstance(f,dict) and matches(f,case)] if isinstance(rows,list) and not reply.get("isError") else []
  if len(selected)!=1:continue
  result=normalize(selected[0],now or datetime.now(UTC))
  if result is not None:return {**result,"source":name}
 return {"state":"Stato non disponibile","source":None}

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

class Client:
 def __init__(self):
  self.headers={"Content-Type":"application/json","Accept":"application/json, text/event-stream","User-Agent":"NextDo-FlightStatus/0.1"}
  self.opener=build_opener(NoRedirect())
  self.ident=0
  self.deadline=time.monotonic()+35
  result=self.exchange("initialize",{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"NextDo","version":"0.1"}},True)
  self.headers["MCP-Protocol-Version"]=result["protocolVersion"]
  self.exchange("notifications/initialized",{},False)
 def exchange(self,method,params,response=True):
  self.ident+=1;ident=self.ident
  message={"jsonrpc":"2.0","method":method,"params":params}
  if response:message["id"]=ident
  remaining=self.deadline-time.monotonic()
  if remaining<=0:raise TimeoutError()
  request=Request(URL,data=json.dumps(message).encode(),headers=self.headers)
  with self.opener.open(request,timeout=min(10,remaining)) as r:
   session=r.headers.get("Mcp-Session-Id")
   if session:self.headers["Mcp-Session-Id"]=session
   if not response:return None
   if r.headers.get_content_type()=="text/event-stream":
    lines=[];size=0;message=None
    while time.monotonic()<self.deadline:
     raw=r.readline(262145);size+=len(raw)
     if not raw or size>262144:break
     line=raw.decode().rstrip("\r\n")
     if line.startswith("data:"):lines.append(line[5:].lstrip(" "))
     elif not line and lines:
      candidate=json.loads("\n".join(lines));lines=[]
      if obj(candidate).get("id")==ident:message=candidate;break
   else:
    raw=r.read(262145)
    if len(raw)>262144:raise ValueError("Response too large")
    message=json.loads(raw)
   if not isinstance(message,dict) or message.get("id")!=ident or not isinstance(message.get("result"),dict):raise ValueError("Invalid MCP response")
   return message["result"]
 def call(self,name,args):return self.exchange("tools/call",{"name":name,"arguments":args})

class Lookup:
 def __init__(self):
  self.lock=threading.Lock()
  self.cache={}
  self.last_call=-1000
  self.inflight=False
  self.block_until=0
 def check(self,owner,case,force=False):
  key=(owner,case)
  now=time.monotonic()
  with self.lock:
   self.cache={k:v for k,v in self.cache.items() if now-v[0]<600}
   hit=self.cache.get(key)
   if hit and (not force or now-hit[0]<60):return {**hit[1],"cached":True}
   if self.inflight or now<self.block_until or now-self.last_call<10:return {"state":"Attendere prima di un nuovo controllo","source":None,"cached":False}
   self.last_call=now;self.inflight=True
  # Network I/O is outside the trip database lock. No retry on errors/rate limits.
  try:result=evaluate(case,Client().call)
  except (OSError,ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
   result={"state":"Servizio temporaneamente non disponibile","source":None}
   if getattr(exc,"code",None)==429:
    with self.lock:self.block_until=time.monotonic()+300
  finally:
   with self.lock:self.inflight=False
  result.update(checked_at=datetime.now(UTC).isoformat(),cached=False)
  with self.lock:
   if len(self.cache)>=256:self.cache.pop(next(iter(self.cache)))
   self.cache[key]=(time.monotonic(),result)
  return result

def is_flight(b):
 kind=b.get("kind")
 return kind=="flight" or not kind and bool(re.fullmatch(r"volo|voli|flight|volo aereo",str(b.get("type","")).strip(),re.I))

def segment_cases(rows):
 if not isinstance(rows,list) or len(rows)>8:raise HTTPException(400,"Massimo 8 tratte per prenotazione")
 normalized=[];seen=set()
 for row in rows:
  if not isinstance(row,dict) or set(row)!={"number","date","from","to"} or not all(isinstance(v,str) for v in row.values()):raise HTTPException(400,"Tratta non valida")
  n,d,o,a=code(row["number"]),local_day(row["date"]),code(row["from"]),code(row["to"])
  if not re.fullmatch(r"[A-Z0-9]{2}[0-9]{1,4}[A-Z]?",n) or not d or not re.fullmatch(r"[A-Z]{3}",o) or not re.fullmatch(r"[A-Z]{3}",a) or o==a:raise HTTPException(400,"Indicare numero, data locale e codici IATA validi e distinti")
  case=(n,d,o,a)
  if case in seen:raise HTTPException(400,"Tratta duplicata")
  seen.add(case);normalized.append(dict(zip(("number","date","from","to"),case)))
 return normalized

def select_case(booking,index):
 if "flight_segments" not in booking:
  if index is not None:raise HTTPException(409,"Ricaricare le tratte")
  return identity(booking)
 rows=segment_cases(booking["flight_segments"])
 if type(index) is not int or index<0 or index>=len(rows):raise HTTPException(409,"Selezionare una tratta valida")
 return tuple(rows[index][k] for k in ("number","date","from","to"))

def register(app,db,load,read_archive,save,template_catalog,web_owner,mobile_owner):
 from .flight_import import suggest
 lookup=Lookup()
 def attach(prefix,authorize):
  @app.post(prefix+"/trips/{tid}/bookings/{bid}/flight-suggestions")
  def suggest_segments(tid:str,bid:str,req:APIRequest,b:dict):
   owner=authorize(req)
   if set(b)!={"revision"} or type(b["revision"]) is not int:raise HTTPException(400,"Richiesta non valida")
   with db() as c:
    row=load(c,owner,tid)
    if row["revision"]!=b["revision"]:raise HTTPException(409,"Il viaggio è stato modificato: ricaricare")
    m,_,files=read_archive(row["archive"])
    booking=next((x for x in m.get("bookings",[]) if x.get("id")==bid),None)
   if booking is None:raise HTTPException(404,"Prenotazione non trovata")
   if not is_flight(booking):raise HTTPException(400,"Prenotazione non aerea")
   if "flight_segments" in booking:return {"segments":[],"saved":True}
   return suggest(booking,m["trip"],files,identity(booking))
  @app.post(prefix+"/trips/{tid}/bookings/{bid}/flight-segments")
  def edit_segments(tid:str,bid:str,req:APIRequest,b:dict):
   owner=authorize(req)
   if set(b)!={"revision","segments"} or type(b["revision"]) is not int:raise HTTPException(400,"Richiesta non valida")
   rows=segment_cases(b["segments"])
   with db() as c:
    row=load(c,owner,tid)
    if row["revision"]!=b["revision"]:raise HTTPException(409,"Il viaggio è stato modificato: ricaricare")
    m,state,files=read_archive(row["archive"])
    booking=next((x for x in m.get("bookings",[]) if x.get("id")==bid),None)
    if booking is None:raise HTTPException(404,"Prenotazione non trovata")
    if not is_flight(booking):raise HTTPException(400,"Prenotazione non aerea")
    booking["flight_segments"]=rows
    revision=save(c,owner,m,state,files,b["revision"])
    return {"revision":revision,"manifest":m,"state":state,"templates":template_catalog(c,owner)}
  @app.post(prefix+"/trips/{tid}/bookings/{bid}/flight-status")
  def check(tid:str,bid:str,req:APIRequest,b:dict):
   owner=authorize(req)
   with db() as c:
    row=load(c,owner,tid);m,_,_=read_archive(row["archive"])
    booking=next((x for x in m.get("bookings",[]) if x.get("id")==bid),None)
   if booking is None:raise HTTPException(404,"Prenotazione non trovata")
   if set(b)-{"force","segment","revision"} or type(b.get("force",False)) is not bool:raise HTTPException(400,"Richiesta non valida")
   if not is_flight(booking):raise HTTPException(400,"Prenotazione non aerea")
   if "flight_segments" in booking and (type(b.get("revision")) is not int or b["revision"]!=row["revision"]):raise HTTPException(409,"Ricaricare le tratte")
   case=select_case(booking,b.get("segment"))
   if not case:return {"state":"Dati volo da completare","source":None,"needs_identity":True}
   # Avoid remote requests well outside the advertised -7 days / tomorrow window.
   offset=(date.fromisoformat(case[1])-datetime.now(UTC).date()).days
   if offset>2 or offset< -8:return {"state":"Stato non disponibile per questa data","source":None}
   return lookup.check(owner,case,b.get("force",False))
 attach("/api/personal",web_owner)
 attach("/api/mobile/v1",mobile_owner)
