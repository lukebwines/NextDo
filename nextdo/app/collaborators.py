"""Lists-only collaborator directory, independent from password-bearing NextDo accounts."""
from __future__ import annotations
import re,sqlite3
from pathlib import Path
from fastapi import Request
from pydantic import BaseModel,Field
from . import workspace

class CollaboratorIn(BaseModel):
 display_name:str=Field(min_length=1,max_length=120)
 microsoft_upn:str=Field(default="",max_length=254)
 active:bool=True

class CollaboratorCourses(BaseModel):
 collaborator_ids:list[int]=Field(default_factory=list,max_length=200)

class ActivateAccess(BaseModel):
 username:str=Field(min_length=2,max_length=100)
 password:str=Field(min_length=8,max_length=256)

def upgrade(db_path:Path,data_path:Path):
 db=sqlite3.connect(db_path)
 try:
  if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collaborators'").fetchone():
   backup=Path(data_path)/"nextdo-before-collaborators-migration.sqlite3"
   if not backup.exists():
    dest=sqlite3.connect(backup)
    try:db.backup(dest)
    finally:dest.close()
  with db:
   db.execute("PRAGMA foreign_keys=ON")
   db.executescript("""
    CREATE TABLE IF NOT EXISTS collaborators(
      id INTEGER PRIMARY KEY,display_name TEXT NOT NULL,
      microsoft_upn TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,
      linked_user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_collaborator_upn
      ON collaborators(microsoft_upn COLLATE NOCASE) WHERE microsoft_upn!='';
    CREATE TABLE IF NOT EXISTS course_collaborators(
      course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      collaborator_id INTEGER NOT NULL REFERENCES collaborators(id) ON DELETE CASCADE,
      PRIMARY KEY(course_id,collaborator_id));
    CREATE TABLE IF NOT EXISTS project_collaborator_responsibilities(
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      collaborator_id INTEGER NOT NULL REFERENCES collaborators(id) ON DELETE CASCADE,
      PRIMARY KEY(project_id,course_id,collaborator_id));
   """)
 finally:db.close()

def normalize_upn(raw):
 value=raw.strip()
 if value and not re.fullmatch(r"[A-Za-z0-9_.%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",value):
  workspace.fail("UPN Microsoft 365 non valido: verificare l'identificativo",400)
 return value

def register_routes(app,*,conn,user,csrf,ph,record):
 def admin(req):
  u=user(req)
  if u["role"]!="admin":workspace.fail("Operazione riservata all'amministratore")
  return u

 @app.get("/api/collaborators")
 def list_collaborators(req:Request):
  u=user(req)
  with conn() as c:
   fields="id,display_name,microsoft_upn,active,linked_user_id" if u["role"]=="admin" else "id,display_name,active,linked_user_id"
   return [dict(r) for r in c.execute("SELECT "+fields+" FROM collaborators ORDER BY display_name,id")]

 @app.post("/api/collaborators")
 def create_collaborator(b:CollaboratorIn,req:Request):
  u=admin(req);csrf(req)
  with conn() as c:
   try:r=c.execute("INSERT INTO collaborators(display_name,microsoft_upn,active) VALUES(?,?,?)",
     (b.display_name.strip(),normalize_upn(b.microsoft_upn),int(b.active)))
   except sqlite3.IntegrityError:workspace.fail("Identificativo Microsoft già associato",409)
   record(c,u["id"],"create","collaborator",r.lastrowid)
   return {"id":r.lastrowid}

 @app.put("/api/collaborators/{cid}")
 def update_collaborator(cid:int,b:CollaboratorIn,req:Request):
  u=admin(req);csrf(req)
  with conn() as c:
   if not c.execute("SELECT 1 FROM collaborators WHERE id=?",(cid,)).fetchone():workspace.fail("Collaboratore inesistente",404)
   try:c.execute("UPDATE collaborators SET display_name=?,microsoft_upn=?,active=? WHERE id=?",
    (b.display_name.strip(),normalize_upn(b.microsoft_upn),int(b.active),cid))
   except sqlite3.IntegrityError:workspace.fail("Identificativo Microsoft già in uso",409)
   record(c,u["id"],"update","collaborator",cid)
  return {"ok":True}

 @app.get("/api/course-collaborators")
 def list_course_collaborators(req:Request):
  u=user(req)
  if u["role"]!="admin":return []
  with conn() as c:return [dict(r) for r in c.execute(
   "SELECT course_id,collaborator_id FROM course_collaborators ORDER BY course_id,collaborator_id")]

 @app.put("/api/courses/{cid}/collaborators")
 def assign_course_collaborators(cid:int,b:CollaboratorCourses,req:Request):
  u=admin(req);csrf(req)
  ids=list(dict.fromkeys(b.collaborator_ids))
  with conn() as c:
   if not c.execute("SELECT 1 FROM courses WHERE id=? AND active=1",(cid,)).fetchone():
    workspace.fail("CdS inesistente o inattivo",404)
   for colid in ids:
    if not c.execute("SELECT 1 FROM collaborators WHERE id=? AND active=1",(colid,)).fetchone():
     workspace.fail("Collaboratore inattivo o inesistente",400)
   c.execute("DELETE FROM course_collaborators WHERE course_id=?",(cid,))
   c.executemany("INSERT INTO course_collaborators(course_id,collaborator_id) VALUES(?,?)",[(cid,n) for n in ids])
   for colid in ids:
    linked=c.execute("SELECT linked_user_id FROM collaborators WHERE id=?",(colid,)).fetchone()[0]
    if linked:c.execute("INSERT OR IGNORE INTO course_assignees(course_id,user_id) VALUES(?,?)",(cid,linked))
   record(c,u["id"],"assign_collaborators","course",cid)
  return {"ok":True}

 @app.post("/api/collaborators/{cid}/activate-access")
 def activate_access(cid:int,b:ActivateAccess,req:Request):
  u=admin(req);csrf(req)
  workspace.check_password_policy(b.password,"user")
  username=b.username.strip()
  if not re.fullmatch(r"[A-Za-z0-9_.@-]{2,100}",username):
   workspace.fail("Nome utente non valido",400)
  with conn() as c:
   person=c.execute("SELECT * FROM collaborators WHERE id=?",(cid,)).fetchone()
   if not person or not person["active"]:workspace.fail("Collaboratore inattivo o inesistente",404)
   linked=person["linked_user_id"]
   if linked:
    existing=c.execute("SELECT role,active FROM users WHERE id=?",(linked,)).fetchone()
    if not existing or existing["role"]!="user":workspace.fail("Il ruolo collegato richiede una verifica amministrativa",400)
    if existing["active"]:workspace.fail("Accesso NextDo già attivo",409)
    try:c.execute("UPDATE users SET username=?,password=?,active=1 WHERE id=?",(username,ph.hash(b.password),linked))
    except sqlite3.IntegrityError:workspace.fail("Nome utente già in uso",409)
    uid=linked
   else:
    try:uid=c.execute("INSERT INTO users(username,password,display_name,role,active) VALUES(?,?,?,?,1)",
       (username,ph.hash(b.password),person["display_name"],"user")).lastrowid
    except sqlite3.IntegrityError:workspace.fail("Nome utente già in uso",409)
    c.execute("UPDATE collaborators SET linked_user_id=? WHERE id=?",(uid,cid))
   assigned={r[0] for r in c.execute("SELECT course_id FROM course_collaborators WHERE collaborator_id=?",(cid,))}
   assigned.update(r[0] for r in c.execute("SELECT course_id FROM project_collaborator_responsibilities WHERE collaborator_id=?",(cid,)))
   for course_id in assigned:
    c.execute("INSERT OR IGNORE INTO course_assignees(course_id,user_id) VALUES(?,?)",(course_id,uid))
   record(c,u["id"],"activate_access","collaborator",cid)
  return {"ok":True,"user_id":uid}

 @app.post("/api/collaborators/{cid}/deactivate-access")
 def deactivate_access(cid:int,req:Request):
  u=admin(req);csrf(req)
  with conn() as c:
   person=c.execute("SELECT linked_user_id FROM collaborators WHERE id=?",(cid,)).fetchone()
   if not person:workspace.fail("Collaboratore inesistente",404)
   uid=person["linked_user_id"]
   if not uid:workspace.fail("Nessun account NextDo collegato",400)
   existing=c.execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
   if not existing or existing["role"]!="user":workspace.fail("Non è consentito disattivare un amministratore",400)
   c.execute("UPDATE users SET active=0 WHERE id=?",(uid,))
   c.execute("DELETE FROM sessions WHERE user_id=?",(uid,))
   record(c,u["id"],"deactivate_access","collaborator",cid)
  return {"ok":True}
