"""Deletion of accidentally created Lists collaborators: synthetic data only."""
from test_workspace import init,create_course,create_user,sign_in


def create_collaborator(client,headers,name="Synthetic accidental colleague"):
 result=client.post("/api/collaborators",headers=headers,json={
  "display_name":name,"microsoft_upn":"unused@example.org"})
 assert result.status_code==200,result.text
 return result.json()["id"]


def test_unlinked_collaborator_deletion_creates_backup_and_removes_course_links(tmp_path):
 client,headers=init(tmp_path)
 course=create_course(client,headers,"MZ6")
 cid=create_collaborator(client,headers)
 assert client.put(f"/api/courses/{course}/collaborators",headers=headers,
  json={"collaborator_ids":[cid]}).status_code==200
 impact=client.get(f"/api/collaborators/{cid}/deletion-impact")
 assert impact.status_code==200,impact.text
 assert impact.json()["can_delete"] is True
 assert impact.json()["course_assignments"]==1
 assert impact.json()["project_assignments"]==0
 assert impact.json()["linked_account"] is False
 assert client.delete(f"/api/collaborators/{cid}",headers=headers).status_code==400
 deleted=client.delete(f"/api/collaborators/{cid}?confirm=ELIMINA",headers=headers)
 assert deleted.status_code==200,deleted.text
 assert deleted.json()["removed_course_assignments"]==1
 assert deleted.json()["backup_created"] is True
 assert not client.get("/api/collaborators").json()
 assert not client.get("/api/course-collaborators").json()
 assert client.get(f"/api/collaborators/{cid}/deletion-impact").status_code==404
 assert client.delete(f"/api/collaborators/{cid}?confirm=ELIMINA",headers=headers).status_code==404
 assert list((tmp_path/"collaborator-deletion-backups").glob("before-delete-collaborator-*.sqlite3"))
 # The UPN from an accidentally entered collaborator may be used again.
 assert client.post("/api/collaborators",headers=headers,json={
  "display_name":"Replacement synthetic person","microsoft_upn":"unused@example.org"}).status_code==200
 client.close()


def test_collaborator_assigned_to_project_is_protected(tmp_path):
 client,headers=init(tmp_path)
 course=create_course(client,headers,"MZ7")
 cid=create_collaborator(client,headers)
 project=client.post("/api/projects",headers=headers,json={"title":"Synthetic project",
  "scope":"cds","course_ids":[course],
  "collaborator_responsibilities":[{"course_id":course,"collaborator_id":cid}]})
 assert project.status_code==200,project.text
 impact=client.get(f"/api/collaborators/{cid}/deletion-impact")
 assert impact.status_code==200 and not impact.json()["can_delete"]
 assert impact.json()["project_assignments"]==1
 result=client.delete(f"/api/collaborators/{cid}?confirm=ELIMINA",headers=headers)
 assert result.status_code==409 and "progetti" in result.text
 assert client.get("/api/collaborators").json()[0]["id"]==cid
 assert next(p for p in client.get("/api/projects").json()
  if p["id"]==project.json()["id"])["collaborator_responsibilities"]
 assert not list((tmp_path/"collaborator-deletion-backups").glob("*.sqlite3"))
 client.close()


def test_linked_nextdo_account_is_protected_even_when_inactive(tmp_path):
 client,headers=init(tmp_path)
 cid=create_collaborator(client,headers)
 activated=client.post(f"/api/collaborators/{cid}/activate-access",headers=headers,json={
  "username":"synthetic_access","password":"sample user password 123"})
 assert activated.status_code==200,activated.text
 assert client.post(f"/api/collaborators/{cid}/deactivate-access",headers=headers).status_code==200
 assert client.get(f"/api/collaborators/{cid}/deletion-impact").json()["linked_account"]
 assert client.delete(f"/api/collaborators/{cid}?confirm=ELIMINA",headers=headers).status_code==409
 assert client.get("/api/collaborators").json()[0]["linked_user_id"]==activated.json()["user_id"]
 client.close()


def test_only_admin_can_preview_or_delete(tmp_path):
 client,headers=init(tmp_path)
 cid=create_collaborator(client,headers)
 create_user(client,headers,"colleague")
 sign_in(client,headers,"colleague")
 assert client.get(f"/api/collaborators/{cid}/deletion-impact").status_code==403
 assert client.delete(f"/api/collaborators/{cid}?confirm=ELIMINA",headers=headers).status_code==403
 client.cookies.delete("nextdo_session")
 assert client.get(f"/api/collaborators/{cid}/deletion-impact").status_code==401
 client.close()


def test_admin_ui_contains_delete_action_and_impact_preview(tmp_path):
 client,headers=init(tmp_path)
 script=client.get("/assets/workspace-ui.js")
 assert script.status_code==200
 assert "Elimina collaboratore" in script.text
 assert "deletion-impact" in script.text
 assert "Elimina definitivamente" in script.text
 client.close()
