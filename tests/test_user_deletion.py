"""Admin account cleanup. Synthetic users and courses only."""
from test_workspace import init,create_user,create_course,sign_in


def test_unused_account_deletion_keeps_projects_and_removes_memberships(tmp_path):
 client,headers=init(tmp_path)
 uid=create_user(client,headers,"temporary")
 course=create_course(client,headers,"MZ9")
 assert client.put(f"/api/courses/{course}/assignees",headers=headers,
  json={"user_ids":[uid]}).status_code==200
 project=client.post("/api/projects",headers=headers,json={
  "title":"Synthetic project that must stay","scope":"independent","member_ids":[uid]})
 assert project.status_code==200,project.text
 pid=project.json()["id"]
 preview=client.get(f"/api/admin/users/{uid}/deletion-impact")
 assert preview.status_code==200,preview.text
 data=preview.json()
 assert data["can_delete"] is True
 assert data["removable_links"]["CdS associati"]==1
 assert data["removable_links"]["Partecipazioni ai progetti"]==1
 assert data["blocking_references"]["Progetti di cui è proprietario"]==0
 assert client.delete(f"/api/admin/users/{uid}",headers=headers).status_code==400
 delete=client.delete(f"/api/admin/users/{uid}?confirm=ELIMINA",headers=headers)
 assert delete.status_code==200,delete.text
 assert delete.json()["backup_created"] and delete.json()["audit_tombstone_created"]
 assert all(x["id"]!=uid for x in client.get("/api/users").json())
 assert client.get(f"/api/admin/users/{uid}/deletion-impact").status_code==404
 assert uid not in next(p for p in client.get("/api/projects").json() if p["id"]==pid)["member_ids"]
 assert not any(x["user_id"]==uid for x in client.get("/api/course-assignees").json())
 assert list((tmp_path/"user-deletion-backups").glob("before-delete-user-*.sqlite3"))
 import sqlite3
 db=sqlite3.connect(tmp_path/"nextdo.sqlite3")
 assert db.execute("SELECT username FROM deleted_user_audit WHERE user_id=?",(uid,)).fetchone()==("temporary",)
 db.close()
 client.close()


def test_attached_tasks_and_project_responsibilities_block_deletion(tmp_path):
 client,headers=init(tmp_path)
 uid=create_user(client,headers,"worker")
 project=client.post("/api/projects",headers=headers,json={
  "title":"Project with assigned task","scope":"independent"})
 assert project.status_code==200
 tid=client.post("/api/tasks",headers=headers,json={
  "title":"Synthetic task that must not be deleted","scope":"project",
  "project_id":project.json()["id"],"assigned_to":uid})
 assert tid.status_code==200,tid.text
 impact=client.get(f"/api/admin/users/{uid}/deletion-impact").json()
 assert impact["can_delete"] is False
 assert impact["blocking_references"]["Attività assegnate"]==1
 assert client.delete(f"/api/admin/users/{uid}?confirm=ELIMINA",headers=headers).status_code==409
 assert client.get(f"/api/tasks/{tid.json()['id']}").status_code==200
 assert not list((tmp_path/"user-deletion-backups").glob("*.sqlite3"))
 course=create_course(client,headers,"MZ8")
 other=create_user(client,headers,"responsible")
 p=client.post("/api/projects",headers=headers,json={
  "title":"Course project","scope":"cds","course_ids":[course],
  "responsibilities":[{"course_id":course,"user_id":other}]})
 assert p.status_code==200,p.text
 assert client.get(f"/api/admin/users/{other}/deletion-impact").json()[
  "blocking_references"]["Responsabilità nei progetti"]==1
 assert client.delete(f"/api/admin/users/{other}?confirm=ELIMINA",headers=headers).status_code==409
 client.close()


def test_active_or_inactive_account_linked_to_collaborator_is_protected(tmp_path):
 client,headers=init(tmp_path)
 cid=client.post("/api/collaborators",headers=headers,json={
  "display_name":"Synthetic Lists person"}).json()["id"]
 result=client.post(f"/api/collaborators/{cid}/activate-access",headers=headers,json={
  "username":"lists_user","password":"sample user password 123"})
 assert result.status_code==200,result.text
 uid=result.json()["user_id"]
 assert client.get(f"/api/admin/users/{uid}/deletion-impact").json()[
  "blocking_references"]["Collaboratori con account collegato"]==1
 assert client.delete(f"/api/admin/users/{uid}?confirm=ELIMINA",headers=headers).status_code==409
 assert client.post(f"/api/collaborators/{cid}/deactivate-access",headers=headers).status_code==200
 assert client.delete(f"/api/admin/users/{uid}?confirm=ELIMINA",headers=headers).status_code==409
 client.close()


def test_admin_cannot_remove_self_or_last_admin(tmp_path):
 client,headers=init(tmp_path)
 me=client.get("/api/me").json()
 impact=client.get(f"/api/admin/users/{me['id']}/deletion-impact").json()
 assert impact["own_account"] and impact["last_active_admin"]
 assert not impact["can_delete"]
 assert client.delete(f"/api/admin/users/{me['id']}?confirm=ELIMINA",headers=headers).status_code==409
 assert client.get("/api/me").status_code==200
 client.close()


def test_only_admin_may_preview_and_delete_accounts(tmp_path):
 client,headers=init(tmp_path)
 uid=create_user(client,headers,"delete_candidate")
 create_user(client,headers,"regular")
 sign_in(client,headers,"regular")
 assert client.get(f"/api/admin/users/{uid}/deletion-impact").status_code==403
 assert client.delete(f"/api/admin/users/{uid}?confirm=ELIMINA",headers=headers).status_code==403
 client.cookies.delete("nextdo_session")
 assert client.get(f"/api/admin/users/{uid}/deletion-impact").status_code==401
 client.close()


def test_settings_contains_account_deletion_controls(tmp_path):
 client,headers=init(tmp_path)
 script=client.get("/assets/workspace-ui.js")
 assert script.status_code==200
 assert "deleteRegisteredUser" in script.text
 assert "deletion-impact" in script.text
 assert "Elimina definitivamente" in script.text
 client.close()
