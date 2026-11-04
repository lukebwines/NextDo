"""Safe, manual per-project JSON export for the tested Power Automate import.

Files are downloaded to the user's browser. No API calls to SharePoint, no credentials,
no task notes/descriptions, no attachments, no user details and no local state changes.
IDs are stable across repeated exports, so Power Automate can skip existing items.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import Response

from . import workspace


def build_project_export(c, project):
 """Produce the exact JSON envelope validated by the SharePoint pilot."""
 rows=c.execute(
  "SELECT id,title,status,due_at FROM tasks WHERE scope='project' AND project_id=? ORDER BY id",
  (project["id"],)
 ).fetchall()
 by_course={}
 for r in c.execute(
  """SELECT r.course_id,r.user_id,c.code,c.name
     FROM project_responsibilities r
     JOIN courses c ON c.id=r.course_id
     WHERE r.project_id=?
     ORDER BY c.code,c.id,r.user_id""",
  (project["id"],)
 ):
  if r["course_id"] not in by_course:
   by_course[r["course_id"]]={
    "course_code":r["code"],"course_name":r["name"],"responsible_user_ids":[]}
  by_course[r["course_id"]]["responsible_user_ids"].append(r["user_id"])
 tasks=[]
 for row in rows:
  base={"title":row["title"],"status":row["status"],"due_at":row["due_at"]}
  if not by_course:
   # Preserve previously published IDs for projects with no CdS assignments.
   tasks.append({"id":"NEXTDO-T"+str(row["id"]),**base})
  else:
   for course_id,details in by_course.items():
    tasks.append({
     "id":"NEXTDO-T"+str(row["id"])+"-C"+str(course_id),
     **base,
     "project_title":project["title"],
     **details
    })
 return {
  "schema_version":"1.0",
  "source":"NextDo",
  "project":{
   "id":"NEXTDO-P"+str(project["id"]),
   "title":project["title"]
  },
  "tasks":tasks
 }


def register_routes(app, *, conn, user):
 @app.get("/api/projects/{pid}/sharepoint-export")
 def sharepoint_export(pid:int, req:Request):
  u=user(req)
  with conn() as c:
   project=c.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
   if not project:
    raise HTTPException(status_code=404,detail="Progetto inesistente")
   if not workspace.project_can_edit(c,u,project):
    raise HTTPException(status_code=403,detail="Esportazione riservata al responsabile del progetto")
   data=build_project_export(c,project)
  payload=json.dumps(data,ensure_ascii=False,indent=2).encode("utf-8")
  # A new filename on each export triggers the SharePoint 'file created' workflow,
  # while the per-task IDs stay unchanged to avoid duplicates.
  suffix=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")+"-"+secrets.token_hex(3)
  filename="nextdo-project-"+str(pid)+"-"+suffix+".json"
  return Response(payload,media_type="application/json; charset=utf-8",headers={
   "Content-Disposition":'attachment; filename="'+filename+'"',
   "Cache-Control":"no-store, max-age=0",
   "Pragma":"no-cache",
   "X-Content-Type-Options":"nosniff"
  })
