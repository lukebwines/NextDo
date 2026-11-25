"""User-owned launcher preference. No ChatGPT credentials or automation tokens."""
import re
from urllib.parse import urlsplit
from fastapi import HTTPException, Request

def validate(value):
 if not isinstance(value,str) or len(value)>512:raise HTTPException(400,"Collegamento non valido")
 value=value.strip()
 if not value:return ""
 try:
  u=urlsplit(value)
  valid=(u.scheme=="https" and u.netloc=="chatgpt.com" and not u.query and not u.fragment
         and re.fullmatch(r"/(?:g/[A-Za-z0-9_-]+/)?c/[A-Za-z0-9_-]+/?",u.path))
 except ValueError:valid=False
 if not valid:raise HTTPException(400,"Incolla il link privato della conversazione ChatGPT (non un link condiviso).")
 return value

def ensure(c):
 c.execute("CREATE TABLE IF NOT EXISTS assistant_links(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,url TEXT NOT NULL)")
def get(c,uid):
 row=c.execute("SELECT url FROM assistant_links WHERE user_id=?",(uid,)).fetchone()
 return {"url":row["url"] if row else ""}
def register(app,conn,user,csrf):
 with conn() as c:ensure(c)
 @app.get("/api/assistant-link")
 def read(req:Request):
  u=user(req)
  with conn() as c:return get(c,u["id"])
 @app.post("/api/assistant-link")
 def save(req:Request,b:dict):
  u=user(req);csrf(req);url=validate(b.get("url"))
  with conn() as c:
   if url:c.execute("INSERT INTO assistant_links(user_id,url) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET url=excluded.url",(u["id"],url))
   else:c.execute("DELETE FROM assistant_links WHERE user_id=?",(u["id"],))
  return {"url":url}
