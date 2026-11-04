"""NextDo standalone task management application. All content is user-supplied."""
from __future__ import annotations
import csv, io, json, os, re, secrets, shutil, sqlite3, tempfile, unicodedata, zipfile, threading, hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.environ.get('NEXTDO_DATA',str(ROOT/'local_data')))
DATA.mkdir(parents=True,exist_ok=True)
FILES=DATA/'attachments'; FILES.mkdir(exist_ok=True)
DB=DATA/'nextdo.sqlite3'
TZ=ZoneInfo(os.environ.get('NEXTDO_TZ','Europe/Rome'))
PH=PasswordHasher()
SETUP_TOKEN_FILE=DATA/'setup-token'

DB_LOCK=threading.RLock()
app=FastAPI(title='NextDo',docs_url=None,redoc_url=None,openapi_url=None)
class FreshAssets(StaticFiles):
 async def get_response(self,path,scope):
  response=await super().get_response(path,scope)
  response.headers['Cache-Control']='no-store, max-age=0'
  return response

app.mount('/assets',FreshAssets(directory=str(ROOT/'static')),name='assets')

@contextmanager
def conn():
 with DB_LOCK:
  c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=10000')
  try: yield c;c.commit()
  except: c.rollback();raise
  finally:c.close()

def init():
 with conn() as c:
  c.executescript('''PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,display_name TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',active INTEGER NOT NULL DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS groups(id INTEGER PRIMARY KEY,name TEXT NOT NULL,created_by INTEGER REFERENCES users(id));
  CREATE TABLE IF NOT EXISTS memberships(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,role TEXT NOT NULL DEFAULT 'member',PRIMARY KEY(group_id,user_id));
  CREATE TABLE IF NOT EXISTS courses(id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE COLLATE NOCASE,name TEXT NOT NULL,active INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT DEFAULT '',kind TEXT DEFAULT 'task',priority TEXT DEFAULT 'normal',status TEXT DEFAULT 'todo',due_at TEXT,start_at TEXT,owner_id INTEGER NOT NULL REFERENCES users(id),assigned_to INTEGER REFERENCES users(id),group_id INTEGER REFERENCES groups(id),completion_mode TEXT DEFAULT 'global',display_enabled INTEGER DEFAULT 0,recurrence TEXT DEFAULT 'none',labels TEXT DEFAULT '[]',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS task_courses(task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,done INTEGER DEFAULT 0,PRIMARY KEY(task_id,course_id));
  CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY,task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,filename TEXT NOT NULL,stored TEXT NOT NULL,mime TEXT,size INTEGER,uploader INTEGER REFERENCES users(id),created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY,task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,minutes_before INTEGER NOT NULL,notified_at TEXT,UNIQUE(task_id,minutes_before));
  CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,message TEXT NOT NULL,seen INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor_id INTEGER,action TEXT NOT NULL,object_type TEXT,object_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
  CREATE TABLE IF NOT EXISTS display_keys(key_hash TEXT PRIMARY KEY,name TEXT NOT NULL,group_id INTEGER REFERENCES groups(id),created_by INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP,revoked INTEGER DEFAULT 0);
  CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at);
  CREATE INDEX IF NOT EXISTS idx_tasks_group ON tasks(group_id);
  ''')
def migrate_legacy_database():
 # Preserve installations created from the earlier public 0.1.2-test schema.
 # No CdS content is copied into source control: this operates only on local /data.
 if not DB.exists():return
 db=sqlite3.connect(DB,timeout=20)
 try:
  tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
  if 'users' not in tables:return
  cols=lambda tab:{r[1] for r in db.execute('PRAGMA table_info('+tab+')')}
  if 'display_name' in cols('users'):return
  backup=DATA/'nextdo-before-full-ui-migration.sqlite3'
  if not backup.exists():
   dest=sqlite3.connect(backup)
   try:db.backup(dest)
   finally:dest.close()
  with db:
   db.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
   db.execute("UPDATE users SET display_name=username WHERE display_name='' ")
   db.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
   db.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT ''")
   if 'sessions' in tables and 'expires_at' not in cols('sessions'):
    db.execute("ALTER TABLE sessions ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''")
    db.execute('UPDATE sessions SET expires_at=expires')
   if 'groups' in tables and 'created_by' not in cols('groups'):
    db.execute('ALTER TABLE groups ADD COLUMN created_by INTEGER')
   if 'tasks' in tables:
    task_cols=cols('tasks')
    additions={
      'kind':"TEXT DEFAULT 'task'", 'assigned_to':'INTEGER',
      'display_enabled':'INTEGER NOT NULL DEFAULT 0',
      'recurrence':"TEXT DEFAULT 'none'", 'labels':"TEXT DEFAULT '[]'",
      'created_at':"TEXT DEFAULT ''",'updated_at':"TEXT DEFAULT ''"
    }
    for name,fieldtype in additions.items():
     if name not in task_cols:db.execute('ALTER TABLE tasks ADD COLUMN '+name+' '+fieldtype)
    if 'published' in task_cols:
     db.execute('UPDATE tasks SET display_enabled=published')
   db.execute('''CREATE TABLE IF NOT EXISTS memberships(group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,role TEXT NOT NULL DEFAULT 'member',PRIMARY KEY(group_id,user_id))''')
   if 'membership' in tables:
    db.execute("INSERT OR IGNORE INTO memberships(group_id,user_id,role) SELECT group_id,user_id,'member' FROM membership")
  print('NEXTDO MIGRAZIONE: schema locale aggiornato; backup creato in /data',flush=True)
 finally:db.close()

migrate_legacy_database()
init()
from . import workspace
workspace.upgrade(DB,DATA)
def ensure_setup_token():
 with conn() as c:
  initial=c.execute('SELECT 1 FROM users LIMIT 1').fetchone() is None
 if not initial:
  SETUP_TOKEN_FILE.unlink(missing_ok=True)
  return
 if not SETUP_TOKEN_FILE.exists():
  try:
   fd=os.open(str(SETUP_TOKEN_FILE),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'w') as handle: handle.write(secrets.token_urlsafe(32))
  except FileExistsError: pass
 print('NEXTDO CODICE PRIMA INSTALLAZIONE: '+SETUP_TOKEN_FILE.read_text().strip(),flush=True)
ensure_setup_token()

def now():return datetime.now(timezone.utc)
def iso():return now().isoformat()
def record(c,uid,action,kind,id):c.execute('INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)',(uid,action,kind,id))
def err(code=403,msg='Operazione non autorizzata'):raise HTTPException(code,msg)
def user(req:Request):
 raw=req.cookies.get('nextdo_session','')
 if not raw:return err(401,'Accesso richiesto')
 hashed=__import__('hashlib').sha256(raw.encode()).hexdigest()
 with conn() as c:
  r=c.execute('SELECT u.id,u.username,u.display_name,u.role,u.active FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?',(hashed,iso())).fetchone()
 if not r or not r['active']:return err(401,'Sessione scaduta')
 return dict(r)
def csrf(req):
 # Cookie-bound request token. SameSite=Strict and Origin/Referer cross-origin checks.
 origin=req.headers.get('origin')
 if origin:
  from urllib.parse import urlsplit
  site=req.headers.get('sec-fetch-site')
  if site and site not in ('same-origin','none'):err(403,'Origine non consentita')
 supplied=req.headers.get('x-nextdo-csrf','')
 cookie=req.cookies.get('nextdo_csrf','')
 if not supplied or not secrets.compare_digest(supplied,cookie):err(403,'Token CSRF mancante')
def mutation(req):user(req);csrf(req)
def is_admin(u):return u['role']=='admin'
def accessible(c,u,t,write=False):
 return workspace.can_read(c,u,t)

def can_edit(c,u,t):
 return workspace.can_write(c,u,t)

def taskdetail(c,t,u=None):
 d=dict(t);d['labels']=json.loads(d['labels'] or '[]');d['courses']=[dict(r) for r in c.execute('SELECT c.id,c.code,c.name,tc.done FROM task_courses tc JOIN courses c ON c.id=tc.course_id WHERE tc.task_id=? ORDER BY c.code',(t['id'],))];d['reminders']=[r['minutes_before'] for r in c.execute('SELECT minutes_before FROM reminders WHERE task_id=?',(t['id'],))];d['attachments']=[dict(r) for r in c.execute('SELECT id,filename,mime,size FROM attachments WHERE task_id=?',(t['id'],))];d['can_edit']=workspace.can_write(c,u,t) if u else False;d['can_move']=workspace.can_move(c,u,t) if u else False;d['can_complete']=(workspace.can_finish(c,u,t) or (t['completion_mode']=='per_course' and bool(c.execute('SELECT 1 FROM task_courses tc JOIN course_assignees ca ON ca.course_id=tc.course_id WHERE tc.task_id=? AND ca.user_id=? LIMIT 1',(t['id'],u['id'])).fetchone()))) if u else False;return d

def check_course_code(code):
 # Historical INCA rule: M followed by 2-3 alphanumerics, including MM? and M??R.
 return bool(re.fullmatch(r'M[A-Z0-9]{2,3}',code.upper()))

def asset_versions():
 return {name:hashlib.sha256((ROOT/'static'/name).read_bytes()).hexdigest()[:12]
         for name in ('style.css','visual-v1.css','file-ui.css','file-tools.js','workspace-ui.css','workspace-ui.js','gantt.css','gantt.js','progress-ui.css','progress-ui.js','app.js')}

@app.get('/',response_class=HTMLResponse)
def home():
 html=(ROOT/'static'/'index.html').read_text(encoding='utf-8')
 for name,digest in asset_versions().items():
  html=html.replace('assets/'+name,'assets/'+name+'?v='+digest)
 return HTMLResponse(html,headers={'Cache-Control':'no-store, max-age=0','Pragma':'no-cache'})

@app.get('/api/build')
def build_details(req:Request):
 user(req)
 return {'version':'0.1.18-test','assets':asset_versions()}
@app.get('/api/setup')
def setup():
 with conn() as c:count=c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
 return {'needs_setup':count==0}
class Credentials(BaseModel):
 username:str=Field(min_length=3,max_length=64)
 # Login must accept existing passwords irrespective of the policy for new accounts.
 password:str=Field(min_length=1,max_length=256)
 display_name:str=Field(default='',max_length=100)
class SetupCredentials(Credentials):
 password:str=Field(min_length=12,max_length=256)
 setup_token:str=Field(min_length=16,max_length=256)

@app.post('/api/setup')
def first_setup(body:SetupCredentials,req:Request):
 csrf(req)
 with conn() as c:
  c.execute('BEGIN IMMEDIATE')
  if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():err(409,'Configurazione già effettuata')
  if not SETUP_TOKEN_FILE.exists():err(503,'Codice installazione non disponibile')
  if not secrets.compare_digest(body.setup_token,SETUP_TOKEN_FILE.read_text().strip()):err(403,'Codice installazione non valido')
  c.execute('INSERT INTO users(username,password,display_name,role) VALUES(?,?,?,?)',(body.username.strip(),PH.hash(body.password),body.display_name.strip() or body.username.strip(),'admin'))
 SETUP_TOKEN_FILE.unlink(missing_ok=True)
 return {'ok':True}
@app.post('/api/login')
def login(body:Credentials,req:Request):
 csrf(req)
 with conn() as c:
  r=c.execute('SELECT * FROM users WHERE username=? AND active=1',(body.username.strip(),)).fetchone()
  try: ok=bool(r and PH.verify(r['password'],body.password))
  except (VerifyMismatchError,VerificationError):ok=False
  if not ok:err(401,'Credenziali non valide')
  token=secrets.token_urlsafe(40);h=__import__('hashlib').sha256(token.encode()).hexdigest();
  expiry=(now()+timedelta(days=7)).isoformat()
  fields={row[1] for row in c.execute('PRAGMA table_info(sessions)')}
  if 'expires' in fields:
   c.execute('INSERT INTO sessions(token_hash,user_id,expires,expires_at) VALUES(?,?,?,?)',(h,r['id'],expiry,expiry))
  else:
   c.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(h,r['id'],expiry))
  record(c,r['id'],'login','user',r['id'])
 res=Response(content=json.dumps({'ok':True}),media_type='application/json');res.set_cookie('nextdo_session',token,httponly=True,secure=req.url.scheme=='https',samesite='strict',max_age=604800,path=req.headers.get('x-ingress-path','/'));return res
@app.post('/api/logout')
def logout(req:Request):
 u=user(req);csrf(req);raw=req.cookies.get('nextdo_session','');h=__import__('hashlib').sha256(raw.encode()).hexdigest()
 with conn() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(h,))
 res=Response(content='{"ok":true}',media_type='application/json');res.delete_cookie('nextdo_session',path=req.headers.get('x-ingress-path','/'));return res
@app.get('/api/csrf')
def csrf_token(req:Request):
 token=req.cookies.get('nextdo_csrf') or secrets.token_urlsafe(32)
 res=Response(content=json.dumps({'csrf':token}),media_type='application/json');res.set_cookie('nextdo_csrf',token,httponly=False,secure=req.url.scheme=='https',samesite='strict',max_age=604800,path=req.headers.get('x-ingress-path','/'));return res
@app.get('/api/me')
def me(req:Request):return user(req)

class NewUser(Credentials):
 password:str=Field(min_length=8,max_length=256)
 role:str='user'
@app.get('/api/users')
def users(req:Request):
 u=user(req)
 with conn() as c:return [dict(r) for r in c.execute('SELECT id,username,display_name,role,active FROM users ORDER BY display_name')]
@app.post('/api/users')
def create_user(b:NewUser,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 if b.role not in ('admin','user'):err(400,'Ruolo non valido')
 if b.role=='admin' and len(b.password)<12:err(400,'La password amministratore deve contenere almeno 12 caratteri')
 with conn() as c:
  try:r=c.execute('INSERT INTO users(username,password,display_name,role) VALUES(?,?,?,?)',(b.username.strip(),PH.hash(b.password),b.display_name.strip() or b.username,b.role))
  except sqlite3.IntegrityError:err(409,'Utente già esistente')
  record(c,u['id'],'create','user',r.lastrowid)
 return {'ok':True}
class GroupIn(BaseModel):name:str=Field(min_length=1,max_length=100)
@app.get('/api/groups')
def groups(req:Request):
 u=user(req)
 with conn() as c:
  sql='SELECT g.* FROM groups g' if is_admin(u) else 'SELECT g.* FROM groups g JOIN memberships m ON g.id=m.group_id WHERE m.user_id=?'
  return [dict(r) for r in c.execute(sql+' ORDER BY g.name',() if is_admin(u) else (u['id'],))]
@app.post('/api/groups')
def create_group(b:GroupIn,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 with conn() as c:
  r=c.execute('INSERT INTO groups(name,created_by) VALUES(?,?)',(b.name.strip(),u['id']));record(c,u['id'],'create','group',r.lastrowid)
 return {'id':r.lastrowid}
class Membership(BaseModel):user_id:int;role:str='member'
@app.post('/api/groups/{gid}/members')
def group_member(gid:int,b:Membership,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):
  with conn() as c:
   r=c.execute('SELECT role FROM memberships WHERE group_id=? AND user_id=?',(gid,u['id'])).fetchone()
   if not r or r['role']!='manager':err()
 if b.role not in ('member','manager'):err(400,'Ruolo non valido')
 with conn() as c:
  try:c.execute('INSERT INTO memberships(group_id,user_id,role) VALUES(?,?,?) ON CONFLICT(group_id,user_id) DO UPDATE SET role=excluded.role',(gid,b.user_id,b.role))
  except sqlite3.IntegrityError:err(400,'Utente o gruppo inesistente')
  record(c,u['id'],'assign','group',gid)
 return {'ok':True}
@app.get('/api/groups/{gid}/members')
def members(gid:int,req:Request):
 u=user(req)
 with conn() as c:
  if not is_admin(u) and not c.execute('SELECT 1 FROM memberships WHERE group_id=? AND user_id=?',(gid,u['id'])).fetchone():err()
  return [dict(r) for r in c.execute('SELECT u.id,u.username,u.display_name,m.role FROM memberships m JOIN users u ON u.id=m.user_id WHERE m.group_id=?',(gid,))]
class CourseIn(BaseModel):code:str;name:str=Field(min_length=1,max_length=200);active:bool=True
@app.get('/api/courses')
def courses(req:Request):
 user(req)
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM courses ORDER BY code')]
@app.post('/api/courses')
def course_create(b:CourseIn,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 code=b.code.strip().upper()
 if not check_course_code(code):err(400,'Codice CdS non ammesso: usare M seguito da 2 o 3 caratteri alfanumerici')
 with conn() as c:
  try:r=c.execute('INSERT INTO courses(code,name,active) VALUES(?,?,?)',(code,b.name.strip(),int(b.active)))
  except sqlite3.IntegrityError:err(409,'Codice CdS già presente')
  if b.active:
   c.execute("INSERT OR IGNORE INTO task_courses(task_id,course_id,done) SELECT id,?,0 FROM tasks WHERE scope='common' AND completion_mode='per_course'",(r.lastrowid,))
   record(c,u['id'],'create','course',r.lastrowid)
 return {'id':r.lastrowid}
@app.put('/api/courses/{cid}')
def course_update(cid:int,b:CourseIn,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 code=b.code.strip().upper()
 if not check_course_code(code):err(400,'Codice non ammesso')
 with conn() as c:
  try:r=c.execute('UPDATE courses SET code=?,name=?,active=? WHERE id=?',(code,b.name.strip(),int(b.active),cid))
  except sqlite3.IntegrityError:err(409,'Codice già presente')
  if not r.rowcount:err(404,'CdS non trovato')
  if b.active:
   c.execute("INSERT OR IGNORE INTO task_courses(task_id,course_id,done) SELECT id,?,0 FROM tasks WHERE scope='common' AND completion_mode='per_course'",(cid,))
   record(c,u['id'],'update','course',cid)
 return {'ok':True}
@app.post('/api/courses/import')
async def course_import(req:Request,file:UploadFile=File(...)):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 raw=await file.read(2_000_001)
 if len(raw)>2_000_000:err(413,'File troppo grande')
 try:content=raw.decode('utf-8-sig')
 except UnicodeDecodeError:err(400,'Usare CSV UTF-8')
 reader=csv.DictReader(io.StringIO(content),delimiter=';' if content.count(';')>content.count(',') else ',')
 if not reader.fieldnames or not {'code','name'}.issubset(reader.fieldnames):err(400,'Colonne richieste: code,name')
 valid=[];rejected=[]
 for i,r in enumerate(reader,2):
  code=(r.get('code') or '').strip().upper();name=(r.get('name') or '').strip()
  if not check_course_code(code) or not name:rejected.append(i)
  else:valid.append((code,name))
 with conn() as c:
  for code,name in valid:
   c.execute('INSERT INTO courses(code,name) VALUES(?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name',(code,name))
   c.execute("INSERT OR IGNORE INTO task_courses(task_id,course_id,done) SELECT t.id,c.id,0 FROM tasks t CROSS JOIN courses c WHERE t.scope='common' AND t.completion_mode='per_course' AND c.active=1")
  record(c,u['id'],'import','course',None)
 return {'imported':len(valid),'rejected_lines':rejected}

class TaskIn(BaseModel):
 title:str=Field(min_length=1,max_length=250)
 description:str=Field(default='',max_length=50000)
 kind:str='task';priority:str='normal';status:str='todo';due_at:Optional[str]=None;start_at:Optional[str]=None
 assigned_to:Optional[int]=None;group_id:Optional[int]=None
 completion_mode:str='global';display_enabled:bool=False;recurrence:str='none'
 scope:str='personal';project_id:Optional[int]=None
 labels:list[str]=Field(default_factory=list);course_ids:list[int]=Field(default_factory=list);reminders:list[int]=Field(default_factory=list)
def validate_task(c,u,b):
 if b.priority not in ('low','normal','high','critical') or b.status not in ('todo','doing','waiting','done') or b.kind not in ('task','note') or b.completion_mode not in ('global','per_course'):err(400,'Valore non valido')
 if b.recurrence not in ('none','daily','weekly','monthly','yearly'):err(400,'Ricorrenza non valida')
 workspace.validate_scope(c,u,b)
 parsed={}
 for key in ('start_at','due_at'):
  value=getattr(b,key)
  if value:
   try:
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    parsed[key]=(d if d.tzinfo else d.replace(tzinfo=TZ)).astimezone(timezone.utc)
   except (ValueError,OverflowError):err(400,'Data non valida')
 if 'start_at' in parsed and 'due_at' in parsed and parsed['start_at']>parsed['due_at']:
  err(400,'La data di inizio non può essere successiva alla scadenza')
 if len(set(b.course_ids))>100 or len(b.labels)>30 or any(len(s)>60 for s in b.labels) or any(n<0 or n>525600 for n in b.reminders):err(400,'Limiti superati')
 if b.group_id:
  if not is_admin(u) and not c.execute('SELECT 1 FROM memberships WHERE group_id=? AND user_id=?',(b.group_id,u['id'])).fetchone():err()
  if b.assigned_to and not is_admin(u) and not c.execute('SELECT 1 FROM memberships WHERE group_id=? AND user_id=?',(b.group_id,b.assigned_to)).fetchone():err(400,'Assegnatario non nel gruppo')
 if b.assigned_to and not b.group_id and b.assigned_to!=u['id'] and not is_admin(u) and b.scope!='project':err(400,'Per assegnare a un collega selezionare un gruppo o progetto')
 if b.display_enabled and not b.group_id:err(400,'Per pubblicare sul monitor selezionare un gruppo')
 if b.course_ids:
  cnt=c.execute('SELECT COUNT(*) FROM courses WHERE id IN ('+','.join('?'*len(set(b.course_ids)))+')',tuple(set(b.course_ids))).fetchone()[0]
  if cnt!=len(set(b.course_ids)):err(400,'CdS inesistente')

def put_task_courses(c,tid,ids):
 c.execute('DELETE FROM task_courses WHERE task_id=? AND course_id NOT IN ('+(','.join('?'*len(ids)) or 'NULL')+')',(tid,*ids))
 for cid in dict.fromkeys(ids):c.execute('INSERT OR IGNORE INTO task_courses(task_id,course_id) VALUES(?,?)',(tid,cid))
def put_reminders(c,tid,mins):
 c.execute('DELETE FROM reminders WHERE task_id=?',(tid,))
 for n in set(mins):c.execute('INSERT INTO reminders(task_id,minutes_before) VALUES(?,?)',(tid,n))
@app.get('/api/tasks')
def tasks(req:Request,course_id:Optional[int]=None,group_id:Optional[int]=None,status:Optional[str]=None,query:Optional[str]=None):
 u=user(req)
 with conn() as c:
  sql='SELECT t.* FROM tasks t WHERE 1=1'
  params=[]
  if course_id:sql+=' AND EXISTS (SELECT 1 FROM task_courses tc WHERE tc.task_id=t.id AND tc.course_id=?)';params.append(course_id)
  if group_id:sql+=' AND t.group_id=?';params.append(group_id)
  if status:sql+=' AND t.status=?';params.append(status)
  if query:sql+=' AND (t.title LIKE ? OR t.description LIKE ?)';params.extend(['%'+query[:100]+'%']*2)
  sql+=' ORDER BY CASE WHEN t.status="done" THEN 1 ELSE 0 END,t.due_at IS NULL,t.due_at,t.id DESC'
  visible=(t for t in c.execute(sql,params) if accessible(c,u,t))
  return [taskdetail(c,t,u) for _,t in zip(range(500),visible)]
@app.post('/api/tasks')
def task_create(b:TaskIn,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  validate_task(c,u,b)
  if b.completion_mode=='per_course' and b.status=='done' and b.scope in ('cds','common'):
   err(400,'Completare i singoli CdS prima di chiudere la scadenza')
  r=c.execute('INSERT INTO tasks(title,description,kind,priority,status,due_at,start_at,owner_id,assigned_to,group_id,completion_mode,display_enabled,recurrence,labels,scope,project_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(b.title.strip(),b.description,b.kind,b.priority,b.status,b.due_at,b.start_at,u['id'],b.assigned_to,b.group_id,b.completion_mode,int(b.display_enabled),b.recurrence,json.dumps(b.labels,ensure_ascii=False),b.scope,b.project_id))
  tid=r.lastrowid
  ids=[r[0] for r in c.execute('SELECT id FROM courses WHERE active=1')] if b.scope=='common' and b.completion_mode=='per_course' else b.course_ids
  put_task_courses(c,tid,ids);put_reminders(c,tid,b.reminders);record(c,u['id'],'create','task',tid)
 return {'id':tid}
@app.get('/api/tasks/{tid}')
def task_get(tid:int,req:Request):
 u=user(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not accessible(c,u,t):err()
  return taskdetail(c,t,u)
@app.put('/api/tasks/{tid}')
def task_update(tid:int,b:TaskIn,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not can_edit(c,u,t):err()
  if not is_admin(u) and t['owner_id']!=u['id']:
   original={r[0] for r in c.execute('SELECT course_id FROM task_courses WHERE task_id=?',(tid,))}
   if b.scope!=t['scope'] or b.project_id!=t['project_id'] or b.assigned_to!=t['assigned_to'] or (t['scope']=='cds' and set(b.course_ids)!=original):
    err(403,'Solo il proprietario o l’amministratore può cambiare ambito, CdS e responsabili')
  validate_task(c,u,b)
  if b.completion_mode=='per_course' and b.status=='done' and b.scope in ('cds','common'):
   progress=c.execute('SELECT COUNT(*),SUM(done) FROM task_courses WHERE task_id=?',(tid,)).fetchone()
   if not progress[0] or progress[1]!=progress[0]:err(400,'Completare i singoli CdS prima di chiudere la scadenza')
  c.execute('UPDATE tasks SET title=?,description=?,kind=?,priority=?,status=?,due_at=?,start_at=?,assigned_to=?,group_id=?,completion_mode=?,display_enabled=?,recurrence=?,labels=?,scope=?,project_id=?,updated_at=? WHERE id=?',(b.title.strip(),b.description,b.kind,b.priority,b.status,b.due_at,b.start_at,b.assigned_to,b.group_id,b.completion_mode,int(b.display_enabled),b.recurrence,json.dumps(b.labels,ensure_ascii=False),b.scope,b.project_id,iso(),tid))
  ids=[r[0] for r in c.execute('SELECT id FROM courses WHERE active=1')] if b.scope=='common' and b.completion_mode=='per_course' else b.course_ids
  put_task_courses(c,tid,ids);put_reminders(c,tid,b.reminders)
  if t['status']!=b.status:
   c.execute('INSERT INTO task_progress(task_id,actor_id,old_status,new_status,note) VALUES(?,?,?,?,?)',(tid,u['id'],t['status'],b.status,''))
  record(c,u['id'],'update','task',tid)
 return {'ok':True}
@app.delete('/api/tasks/{tid}')
def task_delete(tid:int,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not can_edit(c,u,t):err()
  paths=[r['stored'] for r in c.execute('SELECT stored FROM attachments WHERE task_id=?',(tid,))]
  c.execute('DELETE FROM tasks WHERE id=?',(tid,));record(c,u['id'],'delete','task',tid)
 for p in paths:(FILES/p).unlink(missing_ok=True)
 return {'ok':True}
@app.post('/api/tasks/{tid}/complete/{cid}')
def complete_course(tid:int,cid:int,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not accessible(c,u,t):err()
  if t['scope'] not in ('cds','common','group','project'):err()
  if not is_admin(u) and not workspace.owns_course(c,u['id'],cid):err(403,'CdS non assegnato')
  if t['completion_mode']!='per_course':err(400,'Attività a completamento globale')
  course=c.execute('SELECT c.code,tc.done FROM task_courses tc JOIN courses c ON c.id=tc.course_id WHERE tc.task_id=? AND tc.course_id=?',(tid,cid)).fetchone()
  if not course:err(404,'CdS non associato')
  c.execute('UPDATE task_courses SET done=1-done WHERE task_id=? AND course_id=?',(tid,cid))
  total=c.execute('SELECT COUNT(*),SUM(done) FROM task_courses WHERE task_id=?',(tid,)).fetchone()
  next_status='done' if total[0] and total[0]==total[1] else 'doing'
  c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',(next_status,iso(),tid))
  note=('Riapertura CdS: ' if course['done'] else 'Completamento CdS: ')+course['code']
  c.execute('INSERT INTO task_progress(task_id,actor_id,old_status,new_status,note) VALUES(?,?,?,?,?)',(tid,u['id'],t['status'],next_status,note))
  record(c,u['id'],'complete_course','task',tid)
 return {'ok':True}
@app.post('/api/tasks/{tid}/toggle')
def toggle(tid:int,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not workspace.can_finish(c,u,t):err()
  if t['completion_mode']=='per_course' and c.execute('SELECT 1 FROM task_courses WHERE task_id=?',(tid,)).fetchone():err(400,'Completare separatamente i CdS')
  next_status='todo' if t['status']=='done' else 'done'
  c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',(next_status,iso(),tid))
  c.execute('INSERT INTO task_progress(task_id,actor_id,old_status,new_status,note) VALUES(?,?,?,?,?)',(tid,u['id'],t['status'],next_status,''))
  record(c,u['id'],'toggle','task',tid)
 return {'ok':True}

MAX_FILE=15*1024*1024
@app.post('/api/tasks/{tid}/attachments')
async def attach(tid:int,req:Request,file:UploadFile=File(...)):
 u=user(req);csrf(req)
 with conn() as c:
  t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
  if not t:err(404,'Attività non trovata')
  if not can_edit(c,u,t):err()
 allowed={'.pdf','.png','.jpg','.jpeg','.webp','.gif','.bmp','.txt','.csv','.doc','.docx','.xls','.xlsx','.ppt','.pptx','.rtf','.odt','.ods','.odp'}
 filename=re.split(r'[\\\\/]',file.filename or '')[-1].strip()
 if not filename or Path(filename).suffix.lower() not in allowed:err(400,'Formato non consentito')
 payload=await file.read(MAX_FILE+1)
 if len(payload)>MAX_FILE:err(413,'Allegato superiore a 15 MB')
 stored=secrets.token_hex(20)+Path(filename).suffix.lower()
 (FILES/stored).write_bytes(payload)
 with conn() as c:
  r=c.execute('INSERT INTO attachments(task_id,filename,stored,mime,size,uploader) VALUES(?,?,?,?,?,?)',(tid,filename,stored,'application/octet-stream',len(payload),u['id']));record(c,u['id'],'attach','task',tid)
 return {'id':r.lastrowid}
@app.get('/api/attachments/{aid}')
def download(aid:int,req:Request):
 u=user(req)
 with conn() as c:
  r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
  if not r:err(404,'Allegato non trovato')
  t=c.execute('SELECT * FROM tasks WHERE id=?',(r['task_id'],)).fetchone()
  if not t or not accessible(c,u,t):err()
 return FileResponse(FILES/r['stored'],filename=r['filename'],media_type='application/octet-stream',headers={'X-Content-Type-Options':'nosniff','Content-Security-Policy':'sandbox'})
@app.delete('/api/attachments/{aid}')
def remove_attachment(aid:int,req:Request):
 u=user(req);csrf(req)
 with conn() as c:
  r=c.execute('SELECT * FROM attachments WHERE id=?',(aid,)).fetchone()
  if not r:err(404,'Allegato non trovato')
  t=c.execute('SELECT * FROM tasks WHERE id=?',(r['task_id'],)).fetchone()
  if not t or not can_edit(c,u,t):err()
  c.execute('DELETE FROM attachments WHERE id=?',(aid,));record(c,u['id'],'delete_attachment','task',r['task_id'])
 (FILES/r['stored']).unlink(missing_ok=True)
 return {'ok':True}

MONTHS={'gennaio':1,'febbraio':2,'marzo':3,'aprile':4,'maggio':5,'giugno':6,'luglio':7,'agosto':8,'settembre':9,'ottobre':10,'novembre':11,'dicembre':12}
class ExtractIn(BaseModel):text:str=Field(min_length=1,max_length=50000)
@app.post('/api/extract')
def extract(b:ExtractIn,req:Request):
 user(req);csrf(req)
 s=b.text.strip();today=datetime.now(TZ).date();dates=[]
 for m in re.finditer(r'\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b',s):
  try:dates.append(date(int(m[3]),int(m[2]),int(m[1])).isoformat())
  except ValueError:pass
 for m in re.finditer(r'\b(\d{1,2})\s+('+ '|'.join(MONTHS)+r')(?:\s+(\d{4}))?\b',s,re.I):
  year=int(m[3]) if m[3] else today.year
  try:
   d=date(year,MONTHS[m[2].lower()],int(m[1]));d=d.replace(year=year+1) if not m[3] and d<today else d
   dates.append(d.isoformat())
  except ValueError:pass
 lower=s.lower()
 if 'domani' in lower:dates.append((today+timedelta(days=1)).isoformat())
 elif re.search(r'\boggi\b',lower):dates.append(today.isoformat())
 rel=re.search(r'\btra\s+(\d{1,3})\s+giorni\b',lower)
 if rel:dates.append((today+timedelta(days=int(rel[1]))).isoformat())
 priority='critical' if re.search(r'\b(critica|criticità|immediata)\b',lower) else 'high' if re.search(r'\b(urgente|priorità alta|urgentemente)\b',lower) else 'normal'
 recurrence='monthly' if 'ogni mese' in lower or 'mensile' in lower else 'yearly' if 'ogni anno' in lower or 'annuale' in lower else 'weekly' if 'ogni settimana' in lower else 'daily' if 'ogni giorno' in lower else 'none'
 # Ambiguities are never silently resolved; user must review suggestions.
 return {'title':next((line.strip()[:250] for line in s.splitlines() if line.strip()),s[:250]),'description':s,'detected_dates':list(dict.fromkeys(dates)),'priority':priority,'recurrence':recurrence,'needs_confirmation':True,'warning':'Verificare e confermare sempre date e priorità suggerite.'}

@app.get('/api/notifications')
def notifications(req:Request):
 u=user(req)
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(u['id'],))]
@app.post('/api/notifications/{nid}/read')
def read_notification(nid:int,req:Request):
 u=user(req);csrf(req)
 with conn() as c:c.execute('UPDATE notifications SET seen=1 WHERE id=? AND user_id=?',(nid,u['id']))
 return {'ok':True}
@app.post('/api/reminders/process')
def reminders_process(req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 created=0
 with conn() as c:
  rows=c.execute('SELECT r.*,t.title,t.due_at,t.status,t.owner_id,t.assigned_to FROM reminders r JOIN tasks t ON t.id=r.task_id WHERE r.notified_at IS NULL AND t.due_at IS NOT NULL AND t.status!="done"').fetchall()
  for r in rows:
   try:d=datetime.fromisoformat(r['due_at'].replace('Z','+00:00'));d=d.replace(tzinfo=TZ) if d.tzinfo is None else d
   except ValueError:continue
   if now()>=d.astimezone(timezone.utc)-timedelta(minutes=r['minutes_before']):
    for uid in {r['owner_id'],r['assigned_to']} - {None}:
     c.execute('INSERT INTO notifications(user_id,task_id,message) VALUES(?,?,?)',(uid,r['task_id'],'Promemoria: '+r['title']))
    c.execute('UPDATE reminders SET notified_at=? WHERE id=?',(iso(),r['id']));created+=1
 return {'processed':created}
@app.post('/api/recurrences/process')
def recurring_process(req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 generated=0
 with conn() as c:
  items=c.execute('SELECT * FROM tasks WHERE status="done" AND recurrence!="none" AND due_at IS NOT NULL').fetchall()
  for t in items:
   try:dt=datetime.fromisoformat(t['due_at'].replace('Z','+00:00'))
   except ValueError:continue
   if t['recurrence']=='daily':n=dt+timedelta(days=1)
   elif t['recurrence']=='weekly':n=dt+timedelta(days=7)
   else:
    import calendar
    y=dt.year+(dt.month//12 if t['recurrence']=='monthly' else 1)
    m=dt.month%12+1 if t['recurrence']=='monthly' else dt.month
    n=dt.replace(year=y,month=m,day=min(dt.day,calendar.monthrange(y,m)[1]))
   # Keep the planned duration when advancing recurring activities.
   shifted_start=None
   if t['start_at']:
    try:shifted_start=(datetime.fromisoformat(t['start_at'].replace('Z','+00:00'))+(n-dt)).isoformat()
    except ValueError:shifted_start=t['start_at']
   c.execute('UPDATE tasks SET status="todo",due_at=?,start_at=?,updated_at=? WHERE id=?',(n.isoformat(),shifted_start,iso(),t['id']))
   c.execute('UPDATE task_courses SET done=0 WHERE task_id=?',(t['id'],))
   c.execute('UPDATE reminders SET notified_at=NULL WHERE task_id=?',(t['id'],))
   record(c,u['id'],'advance_recurrence','task',t['id']);generated+=1
 return {'advanced':generated}

@app.post('/api/displays')
def display_create(req:Request,b:dict):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 name=str(b.get('name','Display'))[:100];gid=b.get('group_id')
 if gid is not None and not isinstance(gid,int):err(400,'Gruppo non valido')
 token=secrets.token_urlsafe(40);hashed=__import__('hashlib').sha256(token.encode()).hexdigest()
 with conn() as c:c.execute('INSERT INTO display_keys(key_hash,name,group_id,created_by) VALUES(?,?,?,?)',(hashed,name,gid,u['id']))
 return {'token':token,'warning':'Salvare il token: non verrà più mostrato.'}
@app.get('/api/displays')
def display_list(req:Request):
 u=user(req)
 if not is_admin(u):err()
 with conn() as c:return [dict(r) for r in c.execute('SELECT name,group_id,created_at,revoked,substr(key_hash,1,12) AS identifier FROM display_keys')]
@app.post('/api/displays/revoke/{keyprefix}')
def display_revoke(keyprefix:str,req:Request):
 u=user(req);csrf(req)
 if not is_admin(u):err()
 with conn() as c:c.execute('UPDATE display_keys SET revoked=1 WHERE substr(key_hash,1,12)=?',(keyprefix,))
 return {'ok':True}
@app.get('/api/display/{token}')
def display_data(token:str):
 if len(token)>200:err(404)
 h=__import__('hashlib').sha256(token.encode()).hexdigest()
 with conn() as c:
  k=c.execute('SELECT * FROM display_keys WHERE key_hash=? AND revoked=0',(h,)).fetchone()
  if not k:err(401,'Monitor non autorizzato')
  sql='SELECT t.id,t.title,t.due_at,t.priority,t.status FROM tasks t WHERE t.display_enabled=1 AND t.group_id IS NOT NULL AND t.status!="done"'
  args=[]
  if k['group_id'] is not None:sql+=' AND t.group_id=?';args.append(k['group_id'])
  sql+=' ORDER BY t.due_at IS NULL,t.due_at LIMIT 50'
  return {'display':k['name'],'tasks':[dict(r) for r in c.execute(sql,args)]}
@app.get('/display/{token}',response_class=HTMLResponse)
def display_page(token:str):
 return (ROOT/'static'/'display.html').read_text(encoding='utf-8')
@app.get('/api/audit')
def audit(req:Request):
 u=user(req)
 if not is_admin(u):err()
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 200')]
@app.get('/api/backup')
def backup(req:Request):
 u=user(req)
 if not is_admin(u):err()
 with tempfile.TemporaryDirectory() as tmp:
  safe=Path(tmp)/'database.sqlite3'
  with conn() as c:
   dest=sqlite3.connect(safe)
   try:c.backup(dest)
   finally:dest.close()
  output=io.BytesIO()
  with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as z:
   z.write(safe,'database.sqlite3')
   for f in FILES.iterdir():
    if f.is_file():z.write(f,'attachments/'+f.name)
 return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="nextdo-backup.zip"','Cache-Control':'no-store'})

# Importa archivi ZIP creati da NextDo; i backup del Supervisor Home Assistant sono distinti.
from .backup_restore import register_restore_routes
register_restore_routes(app,user=user,csrf=csrf,db_path=DB,attachments_path=FILES,data_path=DATA,db_lock=DB_LOCK)

# Workspaces, course ownership, Kanban projects and user account management.
workspace.register_routes(app,conn=conn,user=user,csrf=csrf,ph=PH,record=record)
from . import progress
progress.register_routes(app,conn=conn,user=user,csrf=csrf,record=record)
from . import microsoft_lists
microsoft_lists.register_routes(app,user=user,csrf=csrf,data_path=DATA)
from . import sharepoint_export
sharepoint_export.register_routes(app,conn=conn,user=user)
