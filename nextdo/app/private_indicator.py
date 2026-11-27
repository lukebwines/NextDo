"""Opt-in, read-only Home Assistant indicator. Never returns personal records."""
from datetime import datetime
import hashlib
import secrets
from fastapi import Request,HTTPException
from fastapi.responses import JSONResponse

def ensure(c):
 c.execute("CREATE TABLE IF NOT EXISTS private_indicator (owner_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, credential_digest TEXT NOT NULL UNIQUE)")

def active(items,now,tz):
 for item in items:
  if item["status"]=="done":continue
  if item.get("snoozed_until"):
   try:
    if datetime.fromisoformat(item["snoozed_until"]).replace(tzinfo=tz)>now:continue
    return True
   except (ValueError,TypeError):pass
  if item["status"]=="review" or item["priority"]=="urgent":return True
  value=item.get("due_at")
  if value:
   try:
    due=datetime.fromisoformat(value)
    if len(value)==10:due=due.replace(hour=9)
    if due.replace(tzinfo=tz).timestamp()-now.timestamp()<=86400:return True
   except (ValueError,TypeError,OverflowError):pass
 return False

def register(app,conn,web_owner):
 from . import private_items
 def digest(value):return hashlib.sha256(value.encode()).hexdigest()
 @app.get("/api/personal/ha-indicator")
 def indicator(req:Request):
  header=req.headers.get("authorization","")
  if not header.startswith("Bearer ") or len(header)!=50:raise HTTPException(401,"Indicatore non autorizzato")
  with conn() as c:
   row=c.execute("SELECT p.owner_id FROM private_indicator p JOIN users u ON p.owner_id=u.id WHERE p.credential_digest=? AND u.active=1",(digest(header[7:]),)).fetchone()
   if not row:raise HTTPException(401,"Indicatore non autorizzato")
   state=active(private_items.list_items(c,row[0]),datetime.now(private_items.TZ),private_items.TZ)
  return JSONResponse({"active":state},headers={"Cache-Control":"no-store, private"})
 @app.get("/api/personal/ha-indicator/settings")
 def settings(req:Request):
  identity=web_owner(req,False)
  with conn() as c:
   uid=private_items.owner_id(c,identity)
   return {"enabled":bool(c.execute("SELECT 1 FROM private_indicator WHERE owner_id=?",(uid,)).fetchone())}
 @app.post("/api/personal/ha-indicator/settings")
 def configure(req:Request,b:dict):
  identity=web_owner(req,True)
  action=b.get("action")
  if action not in ("generate","revoke"):raise HTTPException(400,"Azione non valida")
  with conn() as c:
   uid=private_items.owner_id(c,identity)
   c.execute("DELETE FROM private_indicator WHERE owner_id=?",(uid,))
   if action=="revoke":return {"enabled":False}
   value=secrets.token_urlsafe(32)
   c.execute("INSERT INTO private_indicator VALUES(?,?)",(uid,digest(value)))
  return JSONResponse({"enabled":True,"credential":value},headers={"Cache-Control":"no-store, private"})
