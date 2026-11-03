"""NextDo development API. Local-only CdS registry; no course seed data."""
import os, sqlite3, secrets, hashlib, json, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from argon2 import PasswordHasher

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.environ.get("NEXTDO_DATA","/data"))
DATA.mkdir(parents=True,exist_ok=True)
DB=DATA/"nextdo.sqlite3"
hasher=PasswordHasher()
app=FastAPI(title="NextDo development",docs_url=None,redoc_url=None,openapi_url=None)
app.mount("/assets",StaticFiles(directory=str(ROOT/"static")),name="assets")

def connect():
 c=sqlite3.connect(DB)
 c.row_factory=sqlite3.Row
 c.execute("PRAGMA foreign_keys=ON")
 return c

with connect() as c:
 c.executescript("""
 CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user');
 CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),expires TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS membership(group_id INTEGER REFERENCES groups(id),user_id INTEGER REFERENCES users(id),PRIMARY KEY(group_id,user_id));
 CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE,name TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',priority TEXT NOT NULL DEFAULT 'normal',status TEXT NOT NULL DEFAULT 'todo',due_at TEXT,owner_id INTEGER NOT NULL REFERENCES users(id),group_id INTEGER REFERENCES groups(id),published INTEGER NOT NULL DEFAULT 0,completion_mode TEXT NOT NULL DEFAULT 'global');
 CREATE TABLE IF NOT EXISTS task_courses(task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,course_id INTEGER REFERENCES courses(id),done INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(task_id,course_id));
 CREATE TABLE IF NOT EXISTS display_tokens(hash TEXT PRIMARY KEY,group_id INTEGER REFERENCES groups(id),revoked INTEGER NOT NULL DEFAULT 0);
 """)

def fail(code=403,detail="Operazione non autorizzata"):
 raise HTTPException(status_code=code,detail=detail)

def csrf(req):
 a=req.headers.get("x-nextdo-csrf","")
 b=req.cookies.get("nextdo_csrf","")
 if not a or not secrets.compare_digest(a,b):fail(403,"CSRF token richiesto")
 origin=req.headers.get("origin")
 if origin:
  from urllib.parse import urlsplit
  if urlsplit(origin).netloc!=req.headers.get("host"):fail(403,"Origine non consentita")

def identity(req):
 raw=req.cookies.get("nextdo_session","")
 if not raw:fail(401,"Login richiesto")
 h=hashlib.sha256(raw.encode()).hexdigest()
 with connect() as c:
  u=c.execute("SELECT u.id,u.username,u.role FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires>?",(h,datetime.now(timezone.utc).isoformat())).fetchone()
 if not u:fail(401,"Sessione non valida")
 return dict(u)

def admin(req):
 u=identity(req)
 if u["role"]!="admin":fail()
 return u

def can_view(c,u,t):
 return u["role"]=="admin" or t["owner_id"]==u["id"] or (t["group_id"] is not None and bool(c.execute("SELECT 1 FROM membership WHERE group_id=? AND user_id=?",(t["group_id"],u["id"])).fetchone()))

class Credentials(BaseModel):
 username:str=Field(min_length=3,max_length=64)
 password:str=Field(min_length=12,max_length=256)

class Course(BaseModel):
 code:str
 name:str=Field(min_length=1,max_length=200)

class Group(BaseModel):
 name:str=Field(min_length=1,max_length=100)

class Task(BaseModel):
 title:str=Field(min_length=1,max_length=250)
 description:str=""
 priority:str="normal"
 due_at:str|None=None
 group_id:int|None=None
 published:bool=False
 completion_mode:str="global"
 course_ids:list[int]=Field(default_factory=list)

@app.get("/")
def index():
 return FileResponse(ROOT/"static"/"index.html")

@app.get("/api/csrf")
def csrf_issue(req:Request):
 token=secrets.token_urlsafe(24)
 from fastapi.responses import JSONResponse
 response=JSONResponse({"csrf":token})
 response.set_cookie("nextdo_csrf",token,samesite="strict",secure=req.url.scheme=="https")
 return response

@app.get("/api/setup")
def setup_info():
 with connect() as c:return {"needs_setup":c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==0}

@app.post("/api/setup")
def setup(b:Credentials,req:Request):
 csrf(req)
 with connect() as c:
  if c.execute("SELECT 1 FROM users").fetchone():fail(409,"Configurazione già effettuata")
  c.execute("INSERT INTO users(username,password,role) VALUES(?,?,'admin')",(b.username,hasher.hash(b.password)))
 return {"ok":True}

@app.post("/api/login")
def login(b:Credentials,req:Request):
 csrf(req)
 with connect() as c:u=c.execute("SELECT * FROM users WHERE username=?",(b.username,)).fetchone()
 if not u:fail(401,"Credenziali non valide")
 try:hasher.verify(u["password"],b.password)
 except Exception:fail(401,"Credenziali non valide")
 token=secrets.token_urlsafe(40)
 exp=(datetime.now(timezone.utc)+timedelta(hours=12)).isoformat()
 with connect() as c:c.execute("INSERT INTO sessions VALUES(?,?,?)",(hashlib.sha256(token.encode()).hexdigest(),u["id"],exp))
 from fastapi.responses import JSONResponse
 response=JSONResponse({"ok":True,"role":u["role"]})
 response.set_cookie("nextdo_session",token,httponly=True,samesite="strict",secure=req.url.scheme=="https",max_age=43200)
 return response

@app.get("/api/me")
def me(req:Request):return identity(req)

@app.get("/api/courses")
def courses(req:Request):
 identity(req)
 with connect() as c:return [dict(r) for r in c.execute("SELECT * FROM courses ORDER BY code")]

@app.post("/api/courses")
def add_course(b:Course,req:Request):
 admin(req);csrf(req)
 code=b.code.strip().upper()
 if not re.fullmatch(r"M[A-Z0-9]{2,3}",code):fail(400,"Codice non valido")
 with connect() as c:
  if c.execute("SELECT 1 FROM courses WHERE code=?",(code,)).fetchone():fail(409,"Corso esistente")
  cur=c.execute("INSERT INTO courses(code,name) VALUES(?,?)",(code,b.name.strip()))
 return {"id":cur.lastrowid}

@app.post("/api/groups")
def add_group(b:Group,req:Request):
 admin(req);csrf(req)
 with connect() as c:cur=c.execute("INSERT INTO groups(name) VALUES(?)",(b.name,))
 return {"id":cur.lastrowid}

@app.get("/api/groups")
def groups(req:Request):
 u=identity(req)
 with connect() as c:
  if u["role"]=="admin":rs=c.execute("SELECT * FROM groups").fetchall()
  else:rs=c.execute("SELECT g.* FROM groups g JOIN membership m ON m.group_id=g.id WHERE m.user_id=?",(u["id"],)).fetchall()
 return [dict(x) for x in rs]

@app.post("/api/tasks")
def create_task(b:Task,req:Request):
 u=identity(req);csrf(req)
 if b.priority not in ("low","normal","high","critical"):fail(400,"Priorità non valida")
 if b.completion_mode not in ("global","per_course"):fail(400,"Modalità non valida")
 with connect() as c:
  if b.group_id is not None and u["role"]!="admin" and not c.execute("SELECT 1 FROM membership WHERE group_id=? AND user_id=?",(b.group_id,u["id"])).fetchone():fail()
  if b.published and b.group_id is None:fail(400,"Serve un gruppo per la pubblicazione")
  if b.course_ids:
   q="SELECT COUNT(*) FROM courses WHERE id IN ("+",".join("?" for _ in b.course_ids)+")"
   if c.execute(q,b.course_ids).fetchone()[0]!=len(set(b.course_ids)):fail(400,"CdS non trovato")
  cur=c.execute("INSERT INTO tasks(title,description,priority,due_at,owner_id,group_id,published,completion_mode) VALUES(?,?,?,?,?,?,?,?)",(b.title,b.description,b.priority,b.due_at,u["id"],b.group_id,int(b.published),b.completion_mode))
  tid=cur.lastrowid
  for cid in set(b.course_ids):c.execute("INSERT INTO task_courses(task_id,course_id) VALUES(?,?)",(tid,cid))
 return {"id":tid}

@app.get("/api/tasks")
def tasks(req:Request,course_id:int|None=None):
 u=identity(req)
 with connect() as c:
  rows=c.execute("SELECT * FROM tasks ORDER BY due_at IS NULL,due_at,id DESC").fetchall()
  out=[]
  for t in rows:
   if not can_view(c,u,t):continue
   if course_id is not None and not c.execute("SELECT 1 FROM task_courses WHERE task_id=? AND course_id=?",(t["id"],course_id)).fetchone():continue
   d=dict(t)
   d["courses"]=[dict(r) for r in c.execute("SELECT c.id,c.code,c.name,tc.done FROM courses c JOIN task_courses tc ON tc.course_id=c.id WHERE tc.task_id=?",(t["id"],))]
   out.append(d)
 return out

@app.post("/api/tasks/{tid}/complete/{cid}")
def complete_course(tid:int,cid:int,req:Request):
 u=identity(req);csrf(req)
 with connect() as c:
  t=c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone()
  if not t:fail(404,"Attività inesistente")
  if not can_view(c,u,t):fail()
  if t["completion_mode"]!="per_course":fail(400,"Modalità globale")
  cur=c.execute("UPDATE task_courses SET done=1 WHERE task_id=? AND course_id=?",(tid,cid))
  if cur.rowcount==0:fail(404,"CdS non associato")
  pending=c.execute("SELECT COUNT(*) FROM task_courses WHERE task_id=? AND done=0",(tid,)).fetchone()[0]
  c.execute("UPDATE tasks SET status=? WHERE id=?",("done" if pending==0 else "doing",tid))
 return {"ok":True}

@app.post("/api/tasks/{tid}/toggle")
def toggle(tid:int,req:Request):
 u=identity(req);csrf(req)
 with connect() as c:
  t=c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone()
  if not t:fail(404,"Attività inesistente")
  if not can_view(c,u,t):fail()
  if t["completion_mode"]=="per_course" and c.execute("SELECT 1 FROM task_courses WHERE task_id=?",(tid,)).fetchone():fail(400,"Completare i singoli CdS")
  c.execute("UPDATE tasks SET status=? WHERE id=?",("todo" if t["status"]=="done" else "done",tid))
 return {"ok":True}

@app.post("/api/displays")
def display_create(req:Request,group_id:int):
 admin(req);csrf(req)
 token=secrets.token_urlsafe(36)
 with connect() as c:
  if not c.execute("SELECT 1 FROM groups WHERE id=?",(group_id,)).fetchone():fail(404,"Gruppo assente")
  c.execute("INSERT INTO display_tokens(hash,group_id) VALUES(?,?)",(hashlib.sha256(token.encode()).hexdigest(),group_id))
 return {"token":token}

@app.get("/api/display/{token}")
def display_data(token:str):
 with connect() as c:
  r=c.execute("SELECT group_id FROM display_tokens WHERE hash=? AND revoked=0",(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
  if not r:fail(401,"Monitor non autorizzato")
  rows=c.execute("SELECT title,due_at,priority,status FROM tasks WHERE published=1 AND group_id=? AND status!='done' ORDER BY due_at",(r["group_id"],)).fetchall()
 return {"tasks":[dict(x) for x in rows]}


class NewUser(Credentials):
 role:str="user"

class Member(BaseModel):
 user_id:int

class ExtractText(BaseModel):
 text:str=Field(min_length=1,max_length=50000)

@app.post("/api/users")
def new_user(b:NewUser,req:Request):
 admin(req);csrf(req)
 if b.role not in ("admin","user"):fail(400,"Ruolo non valido")
 with connect() as c:
  if c.execute("SELECT 1 FROM users WHERE username=?",(b.username,)).fetchone():fail(409,"Utente già presente")
  cur=c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",(b.username,hasher.hash(b.password),b.role))
 return {"id":cur.lastrowid}

@app.get("/api/users")
def list_users(req:Request):
 admin(req)
 with connect() as c:return [dict(r) for r in c.execute("SELECT id,username,role FROM users ORDER BY username")]

@app.post("/api/groups/{gid}/members")
def add_member(gid:int,b:Member,req:Request):
 admin(req);csrf(req)
 with connect() as c:
  if not c.execute("SELECT 1 FROM groups WHERE id=?",(gid,)).fetchone():fail(404,"Gruppo inesistente")
  if not c.execute("SELECT 1 FROM users WHERE id=?",(b.user_id,)).fetchone():fail(404,"Utente inesistente")
  c.execute("INSERT OR IGNORE INTO membership(group_id,user_id) VALUES(?,?)",(gid,b.user_id))
 return {"ok":True}

@app.get("/api/groups/{gid}/members")
def list_members(gid:int,req:Request):
 admin(req)
 with connect() as c:return [dict(r) for r in c.execute("SELECT u.id,u.username FROM users u JOIN membership m ON m.user_id=u.id WHERE m.group_id=? ORDER BY u.username",(gid,))]

@app.post("/api/extract")
def extract_text(b:ExtractText,req:Request):
 identity(req);csrf(req)
 import re
 from datetime import date
 s=b.text.strip()
 found=set()
 for m in re.finditer(r"\\b(\\d{1,2})[/.](\\d{1,2})[/.](\\d{4})\\b",s):
  try:found.add(date(int(m.group(3)),int(m.group(2)),int(m.group(1))).isoformat())
  except ValueError:pass
 for m in re.finditer(r"\\b(20\\d{2})-(\\d{2})-(\\d{2})\\b",s):
  try:found.add(date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat())
  except ValueError:pass
 low=s.lower()
 priority="critical" if any(x in low for x in ("criticissima","priorità critica")) else "high" if any(x in low for x in ("urgente","priorità alta")) else "normal"
 return {"title":s.splitlines()[0][:250],"detected_dates":sorted(found),"priority":priority,"needs_confirmation":True}
