"""NextDo workspaces: personal/private tasks, CdS assignees, shared deadlines and Kanban projects."""
from __future__ import annotations
import shutil,sqlite3,secrets
from datetime import datetime,timezone
from pathlib import Path
from typing import Optional
from fastapi import Request,HTTPException
from pydantic import BaseModel,Field

VALID_SCOPES=('personal','cds','common','project','group')

def fail(message='Non autorizzato',status=403):
 raise HTTPException(status_code=status,detail=message)

def upgrade(db_path:Path,data_path:Path):
 """Idempotent upgrade with one SQLite backup before first schema alteration."""
 db=sqlite3.connect(db_path)
 try:
  cols={r[1] for r in db.execute('PRAGMA table_info(tasks)')}
  if not cols:return
  if 'scope' not in cols or 'project_id' not in cols:
   backup=data_path/'nextdo-before-workspaces-migration.sqlite3'
   if not backup.exists():
    dst=sqlite3.connect(backup)
    try:db.backup(dst)
    finally:dst.close()
  if 'start_at' not in cols:
   backup=data_path/'nextdo-before-gantt-migration.sqlite3'
   if not backup.exists():
    dest=sqlite3.connect(backup)
    try:db.backup(dest)
    finally:dest.close()
  project_columns={r[1] for r in db.execute('PRAGMA table_info(projects)')}
  if 'featured' not in project_columns:
   backup=data_path/'nextdo-before-featured-projects-migration.sqlite3'
   if not backup.exists():
    target=sqlite3.connect(backup)
    try:db.backup(target)
    finally:target.close()
  with db:
   db.execute('PRAGMA foreign_keys=ON')
   db.executescript("""
    CREATE TABLE IF NOT EXISTS course_assignees (
      course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      PRIMARY KEY(course_id,user_id));
    CREATE TABLE IF NOT EXISTS projects (
      id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
      scope TEXT NOT NULL CHECK(scope IN ('cds','common','independent')),
      owner_id INTEGER NOT NULL REFERENCES users(id),
      manager_id INTEGER REFERENCES users(id),
      status TEXT NOT NULL DEFAULT 'doing',due_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS project_courses (
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      PRIMARY KEY(project_id,course_id));
    CREATE TABLE IF NOT EXISTS project_members (
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('member','manager')),
      PRIMARY KEY(project_id,user_id));
    CREATE TABLE IF NOT EXISTS task_progress (
      id INTEGER PRIMARY KEY,
      task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      actor_id INTEGER NOT NULL REFERENCES users(id),
      old_status TEXT NOT NULL,
      new_status TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_task_progress_task ON task_progress(task_id,id);
   """)
   if 'featured' not in project_columns:
    db.execute('ALTER TABLE projects ADD COLUMN featured INTEGER NOT NULL DEFAULT 1')
   if 'scope' not in cols:
    db.execute("ALTER TABLE tasks ADD COLUMN scope TEXT NOT NULL DEFAULT 'personal'")
    db.execute("UPDATE tasks SET scope='cds' WHERE EXISTS (SELECT 1 FROM task_courses tc WHERE tc.task_id=tasks.id)")
    db.execute("UPDATE tasks SET scope='group' WHERE group_id IS NOT NULL AND scope='personal'")
   if 'project_id' not in cols:
    db.execute('ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id)')
   if 'start_at' not in cols:
    db.execute('ALTER TABLE tasks ADD COLUMN start_at TEXT')
   db.execute('CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)')
   db.execute('CREATE INDEX IF NOT EXISTS idx_tasks_scope ON tasks(scope)')
 finally:db.close()

def owns_course(c,uid,cid):
 return bool(c.execute('SELECT 1 FROM course_assignees WHERE user_id=? AND course_id=?',(uid,cid)).fetchone())

def assigned_task_course(c,uid,tid):
 return bool(c.execute("""SELECT 1 FROM task_courses tc JOIN course_assignees ca ON ca.course_id=tc.course_id
  WHERE tc.task_id=? AND ca.user_id=? LIMIT 1""",(tid,uid)).fetchone())

def project_can_view(c,u,p):
 if u['role']=='admin' or p['owner_id']==u['id'] or p['manager_id']==u['id']:return True
 if c.execute('SELECT 1 FROM project_members WHERE project_id=? AND user_id=?',(p['id'],u['id'])).fetchone():return True
 if p['scope']=='common':return True
 if p['scope']=='cds':
  return bool(c.execute("""SELECT 1 FROM project_courses pc
    JOIN course_assignees ca ON ca.course_id=pc.course_id
    WHERE pc.project_id=? AND ca.user_id=? LIMIT 1""",(p['id'],u['id'])).fetchone())
 return False

def project_can_edit(c,u,p):
 if u['role']=='admin' or p['owner_id']==u['id'] or p['manager_id']==u['id']:return True
 return bool(c.execute("SELECT 1 FROM project_members WHERE project_id=? AND user_id=? AND role='manager'",(p['id'],u['id'])).fetchone())

def can_read(c,u,t):
 scope=t['scope'] if 'scope' in t.keys() else 'group'
 if scope=='personal':return t['owner_id']==u['id']
 if u['role']=='admin':return True
 if scope=='common':return True
 if scope=='cds':return assigned_task_course(c,u['id'],t['id'])
 if scope=='project' and t['project_id']:
  p=c.execute('SELECT * FROM projects WHERE id=?',(t['project_id'],)).fetchone()
  return bool(p and project_can_view(c,u,p))
 if t['owner_id']==u['id'] or t['assigned_to']==u['id']:return True
 if t['group_id'] is not None:
  return bool(c.execute('SELECT 1 FROM memberships WHERE group_id=? AND user_id=?',(t['group_id'],u['id'])).fetchone())
 return False

def can_write(c,u,t):
 scope=t['scope'] if 'scope' in t.keys() else 'group'
 if scope=='personal':return t['owner_id']==u['id']
 if u['role']=='admin':return True
 if scope=='common':return t['owner_id']==u['id'] or t['assigned_to']==u['id']
 if scope=='cds':
  return assigned_task_course(c,u['id'],t['id']) and t['assigned_to'] in (None,u['id'])
 if scope=='project' and t['project_id']:
  p=c.execute('SELECT * FROM projects WHERE id=?',(t['project_id'],)).fetchone()
  return bool(p and (project_can_edit(c,u,p) or (t['assigned_to']==u['id'] and project_can_view(c,u,p))))
 if t['assigned_to']==u['id'] or t['owner_id']==u['id']:return True
 if t['group_id']:
  member=c.execute("SELECT role FROM memberships WHERE group_id=? AND user_id=?",(t['group_id'],u['id'])).fetchone()
  return bool(member and member['role']=='manager')
 return False

def can_finish(c,u,t):
 if not can_read(c,u,t):return False
 scope=t['scope']
 if scope=='common' and t['completion_mode']=='global':
  return u['role']=='admin' or t['owner_id']==u['id'] or t['assigned_to']==u['id']
 return can_write(c,u,t)

def validate_scope(c,u,b):
 scope=b.scope
 if scope not in VALID_SCOPES:fail('Ambito non valido',400)
 if scope=='personal':
  if b.course_ids or b.group_id or b.project_id or (b.assigned_to not in (None,u['id'])) or b.display_enabled:
   fail('Una nota o attività personale non può essere condivisa',400)
 if scope=='cds':
  if not b.course_ids or b.project_id:fail('Selezionare almeno un CdS',400)
  if u['role']!='admin' and any(not owns_course(c,u['id'],cid) for cid in b.course_ids):
   fail('CdS non assegnato a questo account')
  if b.assigned_to and not any(owns_course(c,b.assigned_to,cid) for cid in b.course_ids):
   fail('Assegnare prima il CdS al collega prescelto',400)
 if scope=='common':
  if u['role']!='admin':fail('Solo l’amministratore può creare una scadenza comune')
  if b.project_id or b.course_ids:fail('Le scadenze comuni si applicano a tutti i CdS automaticamente',400)
 if scope=='project':
  if not b.project_id or b.course_ids:fail('Selezionare un progetto e non duplicare i CdS',400)
  p=c.execute('SELECT * FROM projects WHERE id=?',(b.project_id,)).fetchone()
  if not p or not project_can_view(c,u,p):fail('Progetto non accessibile')
 if scope=='group' and not b.group_id:fail('Gruppo richiesto',400)
 if b.project_id and scope!='project':fail('Il progetto richiede l’ambito Progetto',400)
 if b.assigned_to and b.assigned_to!=u['id'] and u['role']!='admin':
  if scope=='project':
   p=c.execute('SELECT * FROM projects WHERE id=?',(b.project_id,)).fetchone()
   if not p or not project_can_edit(c,u,p):fail('Solo il responsabile può assegnare attività')
  elif scope!='group':fail('Assegnazione riservata al responsabile')
 if b.display_enabled and scope=='personal':fail('Attività personale non pubblicabile',400)

class Assignment(BaseModel):
 user_ids:list[int]=Field(default_factory=list,max_length=100)

class ProjectIn(BaseModel):
 title:str=Field(min_length=1,max_length=250)
 description:str=Field(default='',max_length=50000)
 scope:str='independent'
 manager_id:Optional[int]=None
 course_ids:list[int]=Field(default_factory=list,max_length=100)
 member_ids:list[int]=Field(default_factory=list,max_length=100)
 due_at:Optional[str]=None
 status:str='doing'
 featured:bool=True

class TaskStatus(BaseModel):
 status:str

class ProgressUpdate(BaseModel):
 status:str
 note:str=Field(default='',max_length=1500)

class PasswordChange(BaseModel):
 current_password:str
 new_password:str=Field(min_length=12,max_length=256)

class PasswordReset(BaseModel):
 new_password:str=Field(min_length=12,max_length=256)

class AccountChange(BaseModel):
 role:str
 active:bool

def register_routes(app,*,conn,user,csrf,ph,record):
 def needadmin(req):
  u=user(req)
  if u['role']!='admin':fail()
  return u
 @app.get('/api/course-assignees')
 def all_course_assignees(req:Request):
  needadmin(req)
  with conn() as c:
   return [dict(r) for r in c.execute('SELECT ca.course_id,ca.user_id,u.display_name FROM course_assignees ca JOIN users u ON u.id=ca.user_id ORDER BY ca.course_id,u.display_name')]
 @app.get('/api/my-courses')
 def my_course_ids(req:Request):
  u=user(req)
  with conn() as c:
   if u['role']=='admin':return [r[0] for r in c.execute('SELECT id FROM courses WHERE active=1')]
   return [r[0] for r in c.execute('SELECT ca.course_id FROM course_assignees ca JOIN courses c ON c.id=ca.course_id WHERE ca.user_id=? AND c.active=1',(u['id'],))]

 @app.put('/api/courses/{cid}/assignees')
 def assign_course(cid:int,b:Assignment,req:Request):
  u=needadmin(req);csrf(req)
  ids=list(dict.fromkeys(b.user_ids))
  with conn() as c:
   if not c.execute('SELECT 1 FROM courses WHERE id=?',(cid,)).fetchone():fail('CdS inesistente',404)
   for uid in ids:
    if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(uid,)).fetchone():fail('Collega non attivo o inesistente',400)
   c.execute('DELETE FROM course_assignees WHERE course_id=?',(cid,))
   c.executemany('INSERT INTO course_assignees(course_id,user_id) VALUES(?,?)',[(cid,uid) for uid in ids])
   record(c,u['id'],'assign','course',cid)
  return {'ok':True,'user_ids':ids}
 def project_data(c,p,current_user=None):
  d=dict(p)
  d['course_ids']=[r[0] for r in c.execute('SELECT course_id FROM project_courses WHERE project_id=?',(p['id'],))]
  d['member_ids']=[r[0] for r in c.execute('SELECT user_id FROM project_members WHERE project_id=?',(p['id'],))]
  d['counts']={r['status']:r['n'] for r in c.execute("SELECT status,COUNT(*) AS n FROM tasks WHERE project_id=? GROUP BY status",(p['id'],))}
  d['can_edit']=project_can_edit(c,current_user,p) if current_user else False
  return d
 def validate_project(c,u,b):
  if b.scope not in ('independent','cds','common'):fail('Ambito progetto non valido',400)
  if b.status not in ('todo','doing','waiting','done'):fail('Stato progetto non valido',400)
  if b.scope=='cds' and not b.course_ids:fail('Selezionare i CdS del progetto',400)
  if b.scope!='cds' and b.course_ids:fail('Questo progetto non richiede CdS',400)
  if b.scope=='common' and u['role']!='admin':fail('Progetti comuni riservati agli amministratori')
  if len(set(b.course_ids))!=len(b.course_ids) or len(set(b.member_ids))!=len(b.member_ids):fail('Assegnazioni duplicate',400)
  if b.scope=='cds':
   for cid in b.course_ids:
    if not c.execute('SELECT 1 FROM courses WHERE id=? AND active=1',(cid,)).fetchone():fail('CdS non attivo',400)
    if u['role']!='admin' and not owns_course(c,u['id'],cid):fail('CdS non assegnato')
  for uid in [*b.member_ids,*([b.manager_id] if b.manager_id else [])]:
   if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(uid,)).fetchone():fail('Partecipante inesistente o disattivato',400)
  if b.due_at:
   try:datetime.fromisoformat(b.due_at.replace('Z','+00:00'))
   except ValueError:fail('Data progetto non valida',400)
 def project_participants(c,pid,owner,manager,b):
  members=set(b.member_ids)|{owner}|({manager} if manager else set())
  c.execute('DELETE FROM project_members WHERE project_id=?',(pid,))
  c.executemany('INSERT INTO project_members(project_id,user_id,role) VALUES(?,?,?)',[(pid,x,'manager' if x in (owner,manager) else 'member') for x in members])
 @app.get('/api/projects')
 def projects(req:Request):
  u=user(req)
  with conn() as c:
   return [project_data(c,p,u) for p in c.execute('SELECT * FROM projects ORDER BY updated_at DESC,id DESC') if project_can_view(c,u,p)]
 @app.post('/api/projects')
 def create_project(b:ProjectIn,req:Request):
  u=user(req);csrf(req)
  with conn() as c:
   validate_project(c,u,b)
   p=c.execute('INSERT INTO projects(title,description,scope,owner_id,manager_id,status,due_at,featured) VALUES(?,?,?,?,?,?,?,?)',(b.title.strip(),b.description,b.scope,u['id'],b.manager_id or u['id'],b.status,b.due_at,int(b.featured)))
   pid=p.lastrowid
   c.executemany('INSERT INTO project_courses(project_id,course_id) VALUES(?,?)',[(pid,cid) for cid in b.course_ids])
   project_participants(c,pid,u['id'],b.manager_id or u['id'],b)
   record(c,u['id'],'create','project',pid)
  return {'id':pid}
 @app.put('/api/projects/{pid}')
 def update_project(pid:int,b:ProjectIn,req:Request):
  u=user(req);csrf(req)
  with conn() as c:
   p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
   if not p:fail('Progetto inesistente',404)
   if not project_can_edit(c,u,p):fail()
   validate_project(c,u,b)
   c.execute('UPDATE projects SET title=?,description=?,scope=?,manager_id=?,status=?,due_at=?,featured=?,updated_at=? WHERE id=?',(b.title.strip(),b.description,b.scope,b.manager_id or p['owner_id'],b.status,b.due_at,int(b.featured),datetime.now(timezone.utc).isoformat(),pid))
   c.execute('DELETE FROM project_courses WHERE project_id=?',(pid,))
   c.executemany('INSERT INTO project_courses(project_id,course_id) VALUES(?,?)',[(pid,cid) for cid in b.course_ids])
   project_participants(c,pid,p['owner_id'],b.manager_id or p['owner_id'],b)
   record(c,u['id'],'update','project',pid)
  return {'ok':True}
 @app.patch('/api/tasks/{tid}/status')
 def task_status(tid:int,b:TaskStatus,req:Request):
  u=user(req);csrf(req)
  if b.status not in ('todo','doing','waiting','done'):fail('Stato non valido',400)
  with conn() as c:
   t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
   if not t:fail('Attività inesistente',404)
   allowed=can_finish(c,u,t) if b.status=='done' else can_write(c,u,t)
   if not allowed:fail()
   if b.status=='done' and t['completion_mode']=='per_course' and c.execute('SELECT 1 FROM task_courses WHERE task_id=?',(tid,)).fetchone():
    fail('Completare separatamente i CdS',400)
   c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',(b.status,datetime.now(timezone.utc).isoformat(),tid))
   record(c,u['id'],'status','task',tid)
  return {'ok':True}
 @app.get('/api/profile')
 def profile(req:Request):
  return user(req)
 @app.post('/api/profile/password')
 def change_password(b:PasswordChange,req:Request):
  u=user(req);csrf(req)
  with conn() as c:
   row=c.execute('SELECT password FROM users WHERE id=?',(u['id'],)).fetchone()
   try:ok=ph.verify(row['password'],b.current_password)
   except Exception:ok=False
   if not ok:fail('Password attuale non corretta',403)
   c.execute('UPDATE users SET password=? WHERE id=?',(ph.hash(b.new_password),u['id']))
   c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
   record(c,u['id'],'password_change','user',u['id'])
  return {'ok':True,'relogin':True}
 @app.put('/api/admin/users/{uid}')
 def change_user(uid:int,b:AccountChange,req:Request):
  u=needadmin(req);csrf(req)
  if b.role not in ('admin','user'):fail('Ruolo non valido',400)
  with conn() as c:
   target=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
   if not target:fail('Utente inesistente',404)
   if target['role']=='admin' and target['active'] and (b.role!='admin' or not b.active):
    n=c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
    if n<=1:fail('Impossibile disattivare l’ultimo amministratore',400)
   c.execute('UPDATE users SET role=?,active=? WHERE id=?',(b.role,int(b.active),uid))
   c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
   record(c,u['id'],'update','user',uid)
  return {'ok':True}
 @app.post('/api/admin/users/{uid}/password')
 def reset_password(uid:int,b:PasswordReset,req:Request):
  u=needadmin(req);csrf(req)
  with conn() as c:
   if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():fail('Utente inesistente',404)
   c.execute('UPDATE users SET password=? WHERE id=?',(ph.hash(b.new_password),uid))
   c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
   record(c,u['id'],'password_reset','user',uid)
  return {'ok':True}
