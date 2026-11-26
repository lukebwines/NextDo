"""Private reminder feed with a separate, limited device credential."""
from datetime import datetime
from zoneinfo import ZoneInfo
import os,hashlib,json,time
from fastapi import Request,HTTPException
from . import private_items
TZ=ZoneInfo(os.environ.get("NEXTDO_TZ","Europe/Rome"))

def due_notices(items,now,secret):
 out=[]
 for item in items:
  if item["status"]=="done":continue
  revision=json.dumps(item,sort_keys=True,ensure_ascii=False)
  marks=[]
  if item["status"]=="review":marks.append("review")
  if item["priority"]=="urgent":marks.append("urgent")
  postponed=item.get("snoozed_until")
  if postponed:
   try:
    seconds=datetime.fromisoformat(postponed).replace(tzinfo=TZ).timestamp()-now.timestamp()
    if seconds>0:continue
    marks=["snooze"] if seconds>=-86400 else []
   except (ValueError,TypeError,OverflowError):pass
  value=None if postponed else item["due_at"]
  if value:
   try:
    due=datetime.fromisoformat(value)
    if len(value)==10:due=due.replace(hour=9)
    seconds=due.replace(tzinfo=TZ).timestamp()-now.timestamp()
    if -86400<=seconds<=0:marks.append("due")
    elif 0<seconds<=900 and item["kind"]=="appointment" and len(value)>10:marks.append("15min")
    elif 0<seconds<=3600 and item["kind"]=="appointment" and len(value)>10:marks.append("1h")
    elif 0<seconds<=86400:marks.append("24h")
   except (ValueError,TypeError,OverflowError):pass
  for mark in marks:out.append({"key":hashlib.sha256((secret+":"+revision+":"+mark).encode()).hexdigest()})
 return out[:500]

def register(app,db,conn,auth,active,token,digest,raw_token):
 @app.post("/api/mobile/v1/private-alerts/enable")
 def enable(req:Request):
  dev=auth(req);raw=token()
  with db() as c:
   if not c.execute("SELECT 1 FROM mobile_devices WHERE id=? AND revoked=0 AND expires>?",(dev["id"],time.time())).fetchone():raise HTTPException(401,"Dispositivo non disponibile")
   c.execute("INSERT OR REPLACE INTO private_alert_tokens VALUES(?,?)",(dev["id"],digest(raw)))
  return {"token":raw,"expires":dev["expires"]}
 @app.post("/api/mobile/v1/private-alerts/disable")
 def disable(req:Request):
  dev=auth(req)
  with db() as c:c.execute("DELETE FROM private_alert_tokens WHERE device_id=?",(dev["id"],))
  return {"ok":True}
 @app.get("/api/mobile/v1/private-alerts")
 def alerts(req:Request):
  h=req.headers.get("authorization","")
  if not h.startswith("Bearer "):raise HTTPException(401,"Credenziale avvisi richiesta")
  key=raw_token(h[7:])
  with db() as c:
   dev=c.execute("SELECT d.* FROM private_alert_tokens t JOIN mobile_devices d ON d.id=t.device_id WHERE t.token_hash=? AND d.revoked=0 AND d.expires>?",(key,time.time())).fetchone()
  if not dev:raise HTTPException(401,"Credenziale avvisi scaduta o revocata")
  active(dev["owner"])
  with conn() as c:items=private_items.list_items(c,private_items.owner_id(c,dev["owner"]))
  return {"items":due_notices(items,datetime.now(TZ),key)}
