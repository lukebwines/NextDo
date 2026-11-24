"""Private, explicitly confirmed Google Timeline imports; never store raw exports."""
import json, math, re, time
from datetime import date, datetime
from fastapi import HTTPException, Request

MAX_RECORDS = 30000
MAX_BYTES = 5 * 1024 * 1024

def invalid():
    raise HTTPException(400, "Cronologia o intervallo non valido")

def iso_date(v):
    if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v): invalid()
    try: return date.fromisoformat(v)
    except ValueError: invalid()

def stamp(v, lo, hi):
    if not isinstance(v, str) or len(v)>40 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})",v): invalid()
    try: t=datetime.fromisoformat(v.replace("Z","+00:00"))
    except ValueError: invalid()
    if not lo<=t.date()<=hi: invalid()
    return t

def coord(v):
    if not isinstance(v, dict) or set(v)!={"lat","lon"}: invalid()
    a,b=v["lat"],v["lon"]
    if type(a) not in (int,float) or type(b) not in (int,float): invalid()
    if not -90<=a<=90 or not -180<=b<=180: invalid()
    return {"lat":float(a),"lon":float(b)}

def normalize(b):
    if not isinstance(b,dict) or set(b)!={"from","to","visits","activities","paths"}: invalid()
    lo,hi=iso_date(b["from"]),iso_date(b["to"])
    if not 0<=(hi-lo).days<=366: invalid()
    out={"from":lo.isoformat(),"to":hi.isoformat(),"visits":[],"activities":[],"paths":[]}
    count=0
    for kind in ("visits","activities","paths"):
        values=b[kind]
        if not isinstance(values,list): invalid()
        seen=set()
        for v in values:
            if kind=="paths":
                if not isinstance(v,list) or not v: invalid()
                count+=len(v)
                if count>MAX_RECORDS: invalid()
                prev=None; item=[]
                for p in v:
                    if not isinstance(p,dict) or set(p)!={"time","lat","lon"}: invalid()
                    t=stamp(p["time"],lo,hi)
                    if prev is not None and t<=prev: invalid()
                    prev=t
                    item.append({"time":p["time"],**coord({"lat":p["lat"],"lon":p["lon"]})})
            else:
                count+=1
                if count>MAX_RECORDS or not isinstance(v,dict): invalid()
                keys={"startTime","endTime"}|({"location"} if kind=="visits" else {"first","last","distanceMeters","mode"})
                if set(v)!=keys: invalid()
                a,z=stamp(v["startTime"],lo,hi),stamp(v["endTime"],lo,hi)
                if z<a: invalid()
                item={"startTime":v["startTime"],"endTime":v["endTime"]}
                if kind=="visits": item["location"]=coord(v["location"])
                else:
                    d,m=v["distanceMeters"],v["mode"]
                    if d is not None and (type(d) not in (int,float) or not 0<=d<=50000000): invalid()
                    if m is not None and (not isinstance(m,str) or not re.fullmatch(r"[A-Z_]{1,60}",m)): invalid()
                    item.update(first=coord(v["first"]),last=coord(v["last"]),distanceMeters=d,mode=m)
            key=json.dumps(item,sort_keys=True,separators=(",",":"),allow_nan=False)
            if key not in seen:
                seen.add(key);out[kind].append(item)
    if not any(out[k] for k in ("visits","activities","paths")): invalid()
    return out

def register(app,*,db,allowed,auth,load):
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS trip_timeline(owner TEXT NOT NULL,trip_id TEXT NOT NULL,data TEXT NOT NULL,updated REAL NOT NULL,PRIMARY KEY(owner,trip_id))")
    @app.post("/api/mobile/v1/trips/{tid}/timeline")
    async def upload(tid:str,req:Request):
        device=auth(req)
        raw=bytearray()
        async for chunk in req.stream():
            if len(raw)+len(chunk)>MAX_BYTES: raise HTTPException(413,"Importazione troppo grande")
            raw.extend(chunk)
        try: b=json.loads(raw)
        except (ValueError,UnicodeError,RecursionError): invalid()
        data=normalize(b)
        payload=json.dumps(data,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        owner=device["owner"]
        with db() as c:
            load(c,owner,tid)
            # Recheck the device and session after reading the request.
            if auth(req)["id"]!=device["id"]: raise HTTPException(401,"Sessione non valida")
            c.execute("INSERT OR REPLACE INTO trip_timeline VALUES(?,?,?,?)",(owner,tid,payload,time.time()))
        return {"ok":True,"visits":len(data["visits"]),"activities":len(data["activities"]),"points":sum(map(len,data["paths"]))}
    @app.get("/api/personal/trips/{tid}/timeline")
    def read(tid:str,req:Request):
        owner=allowed(req)
        with db() as c:
            load(c,owner,tid)
            row=c.execute("SELECT data,updated FROM trip_timeline WHERE owner=? AND trip_id=?",(owner,tid)).fetchone()
        return {"data":json.loads(row["data"]) if row else None,"updated":row["updated"] if row else None}
    @app.post("/api/personal/trips/{tid}/timeline/clear")
    def clear(tid:str,req:Request):
        owner=allowed(req,True)
        with db() as c:
            load(c,owner,tid)
            c.execute("DELETE FROM trip_timeline WHERE owner=? AND trip_id=?",(owner,tid))
        return {"ok":True}
