"""Private, trip-scoped GPS diary. Explicit recorder assignment; no background token."""
import math,re,time
from fastapi import HTTPException,Request

def fail(code,message):
    raise HTTPException(code,message)

def number(v,minimum,maximum):
    return type(v) in (int,float) and minimum <= v <= maximum and math.isfinite(v)

def register(app,*,db,allowed,auth,load):
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS diary_recorders(
          owner TEXT NOT NULL, trip_id TEXT NOT NULL, device_id TEXT NOT NULL,
          PRIMARY KEY(owner,trip_id));
        CREATE TABLE IF NOT EXISTS diary_points(
          owner TEXT NOT NULL, trip_id TEXT NOT NULL, device_id TEXT NOT NULL,
          id TEXT NOT NULL, segment TEXT NOT NULL, timestamp INTEGER NOT NULL,
          latitude REAL NOT NULL, longitude REAL NOT NULL, accuracy REAL NOT NULL,
          PRIMARY KEY(owner,trip_id,device_id,id));
        CREATE INDEX IF NOT EXISTS diary_points_time
          ON diary_points(owner,trip_id,timestamp);
        """)
    @app.get("/api/personal/trips/{tid}/diary")
    def read(tid:str,req:Request,start:int=0,end:int=4102444800000,limit:int=2000,offset:int=0):
        owner=allowed(req)
        if not 0<=start<end or not 1<=limit<=5000 or offset<0:fail(400,"Intervallo non valido")
        with db() as c:
            load(c,owner,tid)
            recorder=c.execute("SELECT device_id FROM diary_recorders WHERE owner=? AND trip_id=?",(owner,tid)).fetchone()
            rows=c.execute("""SELECT id,segment,timestamp,latitude,longitude,accuracy,device_id FROM diary_points
                WHERE owner=? AND trip_id=? AND timestamp>=? AND timestamp<?
                ORDER BY timestamp,device_id,id LIMIT ? OFFSET ?""",(owner,tid,start,end,limit+1,offset)).fetchall()
            return {"recorder":recorder["device_id"] if recorder else None,"points":[dict(r) for r in rows[:limit]],
                    "next_offset":offset+limit if len(rows)>limit else None}
    @app.post("/api/personal/trips/{tid}/diary/recorder")
    def recorder(tid:str,req:Request,b:dict):
        owner=allowed(req,True);device=b.get("device_id")
        with db() as c:
            load(c,owner,tid)
            if device is None:
                c.execute("DELETE FROM diary_recorders WHERE owner=? AND trip_id=?",(owner,tid))
            else:
                if not isinstance(device,str) or not c.execute("SELECT 1 FROM mobile_devices WHERE id=? AND owner=? AND revoked=0 AND expires>?",(device,owner,time.time())).fetchone():
                    fail(400,"Dispositivo non disponibile")
                c.execute("INSERT OR REPLACE INTO diary_recorders VALUES(?,?,?)",(owner,tid,device))
        return {"ok":True}
    @app.get("/api/mobile/v1/trips/{tid}/diary")
    def mobile_status(tid:str,req:Request):
        device=auth(req);owner=device["owner"]
        with db() as c:
            load(c,owner,tid)
            row=c.execute("SELECT device_id FROM diary_recorders WHERE owner=? AND trip_id=?",(owner,tid)).fetchone()
            return {"can_record":bool(row and row["device_id"]==device["id"])}
    @app.post("/api/mobile/v1/trips/{tid}/diary/points")
    def upload(tid:str,req:Request,b:dict):
        device=auth(req);owner=device["owner"];did=device["id"]
        points=b.get("points")
        if not isinstance(points,list) or not 1<=len(points)<=500:fail(400,"Lotto non valido")
        values=[]
        for p in points:
            if not isinstance(p,dict):fail(400,"Punto non valido")
            key=p.get("id");seg=p.get("segment");ts=p.get("timestamp")
            lat=p.get("latitude");lon=p.get("longitude");acc=p.get("accuracy")
            if not all(isinstance(x,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}",x) for x in (key,seg)) or type(ts) is not int or not 0<ts<=int(time.time()*1000)+300000 or not number(lat,-90,90) or not number(lon,-180,180) or not number(acc,0,100000):
                fail(400,"Punto GPS non valido")
            values.append((owner,tid,did,key,seg,ts,lat,lon,acc))
        with db() as c:
            load(c,owner,tid)
            if not c.execute("""SELECT 1 FROM diary_recorders r JOIN mobile_devices d ON d.id=r.device_id
                WHERE r.owner=? AND r.trip_id=? AND r.device_id=? AND d.owner=? AND d.revoked=0 AND d.expires>?""",(owner,tid,did,owner,time.time())).fetchone():
                fail(403,"Dispositivo non autorizzato a registrare il diario")
            c.executemany("INSERT OR IGNORE INTO diary_points VALUES(?,?,?,?,?,?,?,?,?)",values)
        return {"accepted":len(points)}
    @app.post("/api/personal/trips/{tid}/diary/clear")
    def clear(tid:str,req:Request):
        owner=allowed(req,True)
        with db() as c:
            load(c,owner,tid)
            c.execute("DELETE FROM diary_recorders WHERE owner=? AND trip_id=?",(owner,tid))
            c.execute("DELETE FROM diary_points WHERE owner=? AND trip_id=?",(owner,tid))
        return {"ok":True}
