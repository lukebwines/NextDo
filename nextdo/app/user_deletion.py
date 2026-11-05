"""Admin-only deletion of unused login accounts with dependency checks and a local backup.

Linked collaborators and accounts with operational history remain protected.
Deleting an unused account removes membership/assignments, never its projects or tasks.
"""
from __future__ import annotations
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Request, HTTPException


def fail(message, status=403):
 raise HTTPException(status_code=status, detail=message)


def inspect_account(c, uid, actor):
 row=c.execute("SELECT id,username,display_name,role,active FROM users WHERE id=?",(uid,)).fetchone()
 if not row:fail("Account non trovato",404)
 blocks={
  "Attività di cui è proprietario":("SELECT COUNT(*) FROM tasks WHERE owner_id=?",uid),
  "Attività assegnate":("SELECT COUNT(*) FROM tasks WHERE assigned_to=?",uid),
  "Progetti di cui è proprietario":("SELECT COUNT(*) FROM projects WHERE owner_id=?",uid),
  "Progetti di cui è responsabile":("SELECT COUNT(*) FROM projects WHERE manager_id=?",uid),
  "Responsabilità nei progetti":("SELECT COUNT(*) FROM project_responsibilities WHERE user_id=?",uid),
  "Avanzamenti registrati":("SELECT COUNT(*) FROM task_progress WHERE actor_id=?",uid),
  "Allegati caricati":("SELECT COUNT(*) FROM attachments WHERE uploader=?",uid),
  "Gruppi creati":("SELECT COUNT(*) FROM groups WHERE created_by=?",uid),
  "Monitor creati":("SELECT COUNT(*) FROM display_keys WHERE created_by=?",uid),
  "Collaboratori con account collegato":("SELECT COUNT(*) FROM collaborators WHERE linked_user_id=?",uid),
 }
 # Names in this map are intentionally stable and originate from system schema.
 blocking={name:c.execute(sql,(arg,)).fetchone()[0] for name,(sql,arg) in blocks.items()}
 removable={
  "CdS associati":c.execute("SELECT COUNT(*) FROM course_assignees WHERE user_id=?",(uid,)).fetchone()[0],
  "Gruppi di cui è membro":c.execute("SELECT COUNT(*) FROM memberships WHERE user_id=?",(uid,)).fetchone()[0],
  "Partecipazioni ai progetti":c.execute("SELECT COUNT(*) FROM project_members WHERE user_id=?",(uid,)).fetchone()[0],
  "Notifiche personali":c.execute("SELECT COUNT(*) FROM notifications WHERE user_id=?",(uid,)).fetchone()[0],
  "Sessioni attive":c.execute("SELECT COUNT(*) FROM sessions WHERE user_id=?",(uid,)).fetchone()[0],
 }
 own=uid==actor["id"]
 last_admin=bool(row["role"]=="admin" and row["active"] and
  c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1)
 reasons=[]
 if own:reasons.append("Non puoi eliminare l'account con cui hai effettuato l'accesso")
 if last_admin:reasons.append("Non è consentito eliminare l'ultimo amministratore attivo")
 for name,count in blocking.items():
  if count:reasons.append(name+": "+str(count))
 return {
  "id":uid,"username":row["username"],"display_name":row["display_name"],
  "role":row["role"],"active":bool(row["active"]),"own_account":own,
  "last_active_admin":last_admin,"blocking_references":blocking,
  "removable_links":removable,"reasons":reasons,"can_delete":not bool(reasons)
 }


def register_routes(app,*,conn,user,csrf,record,data_path):
 def admin(req):
  u=user(req)
  if u["role"]!="admin":fail("Operazione riservata all'amministratore")
  return u

 @app.get("/api/admin/users/{uid}/deletion-impact")
 def deletion_impact(uid:int,req:Request):
  u=admin(req)
  with conn() as c:
   return inspect_account(c,uid,u)

 @app.delete("/api/admin/users/{uid}")
 def delete_user(uid:int,req:Request,confirm:str=""):
  u=admin(req);csrf(req)
  if confirm!="ELIMINA":fail("Digitare ELIMINA per confermare l'eliminazione",400)
  with conn() as c:
   impact=inspect_account(c,uid,u)
   if not impact["can_delete"]:
    fail("Impossibile eliminare l'account: "+"; ".join(impact["reasons"]),409)
   backup_dir=Path(data_path)/"user-deletion-backups"
   backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
   filename=("before-delete-user-"+str(uid)+"-"+
    datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(4)+".sqlite3")
   backup_path=backup_dir/filename
   fd=os.open(backup_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   os.close(fd)
   try:
    dest=sqlite3.connect(backup_path)
    try:c.backup(dest)
    finally:dest.close()
   except Exception:
    backup_path.unlink(missing_ok=True)
    raise
   # Retain only a minimal immutable audit tombstone so earlier audit rows
   # remain attributable after removing the account from the active directory.
   c.execute("""CREATE TABLE IF NOT EXISTS deleted_user_audit(
    user_id INTEGER PRIMARY KEY, username TEXT NOT NULL,
    display_name TEXT NOT NULL, role TEXT NOT NULL,
    deleted_by INTEGER NOT NULL, deleted_at TEXT NOT NULL)""")
   c.execute("""INSERT INTO deleted_user_audit(
    user_id,username,display_name,role,deleted_by,deleted_at) VALUES(?,?,?,?,?,?)""",
    (uid,impact["username"],impact["display_name"],impact["role"],
     u["id"],datetime.now(timezone.utc).isoformat()))
   try:
    c.execute("DELETE FROM users WHERE id=?",(uid,))
   except sqlite3.IntegrityError:
    fail("Esistono ulteriori collegamenti a questo account: eliminazione interrotta",409)
   record(c,u["id"],"delete","user",uid)
  return {"ok":True,"removed_links":impact["removable_links"],"backup_created":True,
          "audit_tombstone_created":True}
