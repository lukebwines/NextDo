"""Regression tests for synthetic calendar, collaborator, project lifecycle and Lists sync."""
import io,json,time,zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from test_workspace import init,create_course,create_user,sign_in

M="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL="http://schemas.openxmlformats.org/package/2006/relationships"

def calendar_bytes():
 headers=["Macro Processo","Sotto Processo","indicativamente a partire da","SCADENZE",
  "A.A. di riferimento ","Attività ","Destinatario attività","Responsabile attività",
  "Ufficio di riferimento per il supporto","Organo deliberante","Atto amministrativo"]
 def serial(day):
  return (datetime.fromisoformat(day)-datetime(1899,12,30)).days
 wb=ET.Element(f"{{{M}}}workbook")
 sheets=ET.SubElement(wb,f"{{{M}}}sheets")
 ET.SubElement(sheets,f"{{{M}}}sheet",{"name":"Programmazione didattica",
  "sheetId":"1",f"{{{R}}}id":"rId1"})
 rels=ET.Element(f"{{{REL}}}Relationships")
 ET.SubElement(rels,f"{{{REL}}}Relationship",{"Id":"rId1",
  "Type":R+"/worksheet","Target":"worksheets/sheet1.xml"})
 sheet=ET.Element(f"{{{M}}}worksheet")
 data=ET.SubElement(sheet,f"{{{M}}}sheetData")
 def addrow(number,values):
  row=ET.SubElement(data,f"{{{M}}}row",{"r":str(number)})
  for i,value in enumerate(values):
   if value is None:continue
   col=chr(ord('A')+i)
   cell=ET.SubElement(row,f"{{{M}}}c",{"r":f"{col}{number}"})
   if isinstance(value,int):
    ET.SubElement(cell,f"{{{M}}}v").text=str(value)
   else:
    cell.set("t","inlineStr")
    ET.SubElement(ET.SubElement(cell,f"{{{M}}}is"),f"{{{M}}}t").text=value
 addrow(1,headers)
 addrow(2,["PROGRAMMAZIONE","ATT",serial("2028-01-10"),serial("2028-02-10"),"2027/28",
    "Attività sintetica diretta",None,"UO SEGR CDS",None,None,None])
 addrow(3,["PROGRAMMAZIONE","ATT",serial("2028-01-10"),serial("2028-02-10"),"2027/28",
    "Non riguarda la segreteria",None,"ALTRO UFFICIO",None,None,None])
 addrow(4,["PROGRAMMAZIONE","MON",serial("2026-01-01"),serial("2026-02-01"),"2025/26",
    "Attività sintetica in supporto",None,"CPDS","UO SEGR CDS",None,None])
 with io.BytesIO() as buff:
  with zipfile.ZipFile(buff,"w") as z:
   z.writestr("xl/workbook.xml",ET.tostring(wb))
   z.writestr("xl/_rels/workbook.xml.rels",ET.tostring(rels))
   z.writestr("xl/worksheets/sheet1.xml",ET.tostring(sheet))
  return buff.getvalue()

def upload(c,h,payload,path,selected=None):
 files={"file":("calendar.xlsx",payload,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
 kwargs={"headers":h,"files":files}
 if selected is not None:kwargs["data"]={"selected":json.dumps(selected)}
 return c.post(path,**kwargs)

def test_preview_and_idempotent_calendar_import(tmp_path):
 c,h=init(tmp_path)
 content=calendar_bytes()
 result=upload(c,h,content,"/api/calendar-import/preview")
 assert result.status_code==200,result.text
 rows=result.json()["rows"]
 assert len(rows)==2
 future=next(x for x in rows if x["title"]=="Attività sintetica diretta")
 past=next(x for x in rows if x["title"]=="Attività sintetica in supporto")
 assert future["roles"]==["responsabile"] and future["select_by_default"]
 assert past["roles"]==["supporto"] and past["past"] and not past["select_by_default"]
 assert future["due"]=="2028-02-10"
 assert upload(c,h,content,"/api/calendar-import/apply",[future["key"]]).json()["created"]==1
 again=upload(c,h,content,"/api/calendar-import/apply",[future["key"]]).json()
 assert again["created"]==0 and again["skipped"]==1
 tasks=c.get("/api/tasks").json()
 assert len(tasks)==1
 assert tasks[0]["title"]=="Attività sintetica diretta"
 assert "UO SEGR CDS: responsabile" in tasks[0]["description"]
 assert "[DA VERIFICARE]" in tasks[0]["description"]
 assert tasks[0]["scope"]=="personal"
 assert next(x for x in upload(c,h,content,"/api/calendar-import/preview").json()["rows"]
  if x["key"]==future["key"])["already_imported"] is True
 c.close()

def test_promote_archive_restore_delete_with_backup(tmp_path):
 c,h=init(tmp_path)
 created=c.post("/api/tasks",headers=h,json={"title":"Synthetic deadline","scope":"personal",
   "description":"Original verified text","due_at":"2028-03-10T12:00:00+01:00"})
 assert created.status_code==200,created.text
 tid=created.json()["id"]
 result=c.post(f"/api/tasks/{tid}/promote-to-project",headers=h)
 assert result.status_code==200,result.text
 pid=result.json()["project_id"]
 task=c.get(f"/api/tasks/{tid}").json()
 assert task["id"]==tid and task["project_id"]==pid and task["description"]=="Original verified text"
 assert c.post(f"/api/tasks/{tid}/promote-to-project",headers=h).status_code==400
 assert c.post(f"/api/projects/{pid}/archive",headers=h).status_code==200
 project=next(p for p in c.get("/api/projects").json() if p["id"]==pid)
 assert project["archived_at"] is not None
 assert c.post(f"/api/projects/{pid}/restore",headers=h).status_code==200
 assert next(p for p in c.get("/api/projects").json() if p["id"]==pid)["archived_at"] is None
 assert c.delete(f"/api/projects/{pid}",headers=h).status_code==400
 deleted=c.delete(f"/api/projects/{pid}?confirm=ELIMINA",headers=h)
 assert deleted.status_code==200,deleted.text
 assert deleted.json()["deleted_tasks"]==1
 assert c.get(f"/api/tasks/{tid}").status_code==404
 assert list((tmp_path/"project-deletion-backups").glob("before-delete-project-*.sqlite3"))
 c.close()

def test_lists_collaborator_can_be_activated_without_losing_cds(tmp_path):
 c,h=init(tmp_path)
 course=create_course(c,h,"MZ9")
 created=c.post("/api/collaborators",headers=h,json={
  "display_name":"Synthetic Lists person","microsoft_upn":"synthetic@example.org"})
 assert created.status_code==200,created.text
 cid=created.json()["id"]
 assert len(c.get("/api/users").json())==1
 assert c.put(f"/api/courses/{course}/collaborators",headers=h,
  json={"collaborator_ids":[cid]}).status_code==200
 proj=c.post("/api/projects",headers=h,json={"title":"Synthetic Lists task",
  "scope":"cds","course_ids":[course],
  "collaborator_responsibilities":[{"course_id":course,"collaborator_id":cid}]})
 assert proj.status_code==200,proj.text
 pid=proj.json()["id"]
 tid=c.post("/api/tasks",headers=h,json={
  "title":"Synthetic course report","scope":"project","project_id":pid}).json()["id"]
 exported=c.get(f"/api/projects/{pid}/sharepoint-export").json()["tasks"]
 assert len(exported)==1 and exported[0]["id"]==f"NEXTDO-T{tid}-C{course}"
 assert exported[0]["responsible_collaborators"][0]["microsoft_upn"]=="synthetic@example.org"
 assert not exported[0]["responsible_user_ids"]
 sign_in(c,h,"admin")
 assert c.post(f"/api/collaborators/{cid}/activate-access",headers=h,json={
  "username":"lists_person","password":"sample user password 123"}).status_code==200
 assert len(c.get("/api/users").json())==2
 assert c.post(f"/api/collaborators/{cid}/activate-access",headers=h,json={
  "username":"lists_person","password":"sample user password 123"}).status_code==409
 sign_in(c,h,"lists_person")
 visible=c.get("/api/projects").json()
 assert any(p["id"]==pid for p in visible)
 assert c.get(f"/api/tasks/{tid}").status_code==200
 assert "microsoft_upn" not in c.get("/api/collaborators").json()[0]
 assert c.delete(f"/api/projects/{pid}?confirm=ELIMINA",headers=h).status_code==403
 assert c.post("/api/collaborators",headers=h,json={"display_name":"Unauthorized"}).status_code==403
 sign_in(c,h,"admin")
 assert c.post(f"/api/collaborators/{cid}/deactivate-access",headers=h).status_code==200
 assert c.post("/api/login",headers=h,json={
  "username":"lists_person","password":"sample user password 123"}).status_code==401
 assert c.get(f"/api/collaborators").json()[0]["linked_user_id"] is not None
 c.close()

def test_lists_graph_pull_is_read_only_and_updates_rollup(tmp_path,monkeypatch):
 c,h=init(tmp_path)
 a=create_course(c,h,"MZ7");b=create_course(c,h,"MZ8")
 proj=c.post("/api/projects",headers=h,json={"title":"Synthetic project","scope":"cds","course_ids":[a,b]})
 assert proj.status_code==200,proj.text
 pid=proj.json()["id"]
 task=c.post("/api/tasks",headers=h,json={"title":"Synthetic task","scope":"project","project_id":pid})
 assert task.status_code==200,task.text
 tid=task.json()["id"]
 from app import microsoft_lists as graph
 graph.TOKENS.clear()
 adminid=next(x["id"] for x in c.get("/api/users").json() if x["role"]=="admin")
 graph.TOKENS[adminid]={"token":"synthetic-token","until":time.monotonic()+3600}
 monkeypatch.setattr(graph,"read_settings",lambda data:{"site_url":"https://example.sharepoint.com/sites/Synthetic","list_id":"fake"})
 monkeypatch.setattr(graph,"_site_details",lambda config,token:{"id":"synthetic-site"})
 fake=[{"fields":{"NextDoID":f"NEXTDO-T{tid}-C{a}","NextDoStatus":"Completata"}},
       {"fields":{"NextDoID":f"NEXTDO-T{tid}-C{b}","NextDoStatus":"In corso"}}]
 monkeypatch.setattr(graph,"_all_graph",lambda path,token,max_pages=8:
  [{"name":"NextDoID"},{"name":"NextDoStatus"}] if "/columns" in path else fake)
 result=c.post(f"/api/projects/{pid}/sync-lists",headers=h)
 assert result.status_code==200,result.text
 assert result.json()["updated_course_rows"]==2
 detail=c.get(f"/api/tasks/{tid}").json()
 assert {r["course_id"]:r["status"] for r in detail["external_progress"]}=={a:"done",b:"doing"}
 assert detail["status"]=="doing"
 fake[1]["fields"]["NextDoStatus"]="Completata"
 assert c.post(f"/api/projects/{pid}/sync-lists",headers=h).status_code==200
 assert c.get(f"/api/tasks/{tid}").json()["status"]=="done"
 graph.TOKENS.clear()
 c.close()

def test_gantt_child_rows_are_explicit_and_not_simulated(tmp_path):
 c,h=init(tmp_path)
 gantt=c.get("/assets/gantt.js").text
 for expected in ("gantt-expand","Espandi tutto","Comprimi tutto","Non sincronizzato",
                  "collaborator_responsibilities","external_progress"):
  assert expected in gantt
 c.close()
