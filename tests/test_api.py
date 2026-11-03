import importlib
import os
import sys
from fastapi.testclient import TestClient

def app_client(tmp_path):
 os.environ["NEXTDO_DATA"]=str(tmp_path)
 sys.modules.pop("app.main",None)
 module=importlib.import_module("app.main")
 c=TestClient(module.app)
 token=c.get("/api/csrf").json()["csrf"]
 return c,{"x-nextdo-csrf":token}

def test_empty_courses_stay_local(tmp_path):
 c,h=app_client(tmp_path)
 assert c.get("/api/setup").json()["needs_setup"] is True
 assert c.post("/api/setup",headers=h,json={"username":"tester","password":"test-password-long"}).status_code==200
 assert c.post("/api/login",headers=h,json={"username":"tester","password":"test-password-long"}).status_code==200
 assert c.get("/api/courses").json()==[]
 assert c.get("/api/tasks").json()==[]
 assert c.post("/api/tasks",headers=h,json={"title":"Local-only test activity","priority":"normal"}).status_code==200
 assert c.get("/api/tasks").json()[0]["title"]=="Local-only test activity"

def test_csrf_and_display_publication(tmp_path):
 c,h=app_client(tmp_path)
 assert c.post("/api/setup",json={"username":"tester","password":"test-password-long"}).status_code==403
 assert c.post("/api/setup",headers=h,json={"username":"tester","password":"test-password-long"}).status_code==200
 assert c.post("/api/login",headers=h,json={"username":"tester","password":"test-password-long"}).status_code==200
 group=c.post("/api/groups",headers=h,json={"name":"Test workgroup"}).json()["id"]
 token=c.post("/api/displays",headers=h,params={"group_id":group}).json()["token"]
 assert c.get("/api/display/"+token).json()=={"tasks":[]}
 private=c.post("/api/tasks",headers=h,json={"title":"Private test item"}).json()["id"]
 public=c.post("/api/tasks",headers=h,json={"title":"Display test item","group_id":group,"published":True}).json()["id"]
 rows=c.get("/api/display/"+token).json()["tasks"]
 assert len(rows)==1 and rows[0]["title"]=="Display test item"
 assert "description" not in rows[0]
 assert c.get("/api/display/wrong-token").status_code==401

def test_extraction_requires_review(tmp_path):
 c,h=app_client(tmp_path)
 c.post("/api/setup",headers=h,json={"username":"tester","password":"test-password-long"})
 c.post("/api/login",headers=h,json={"username":"tester","password":"test-password-long"})
 data=c.post("/api/extract",headers=h,json={"text":"Urgente: completare entro 15/12/2030"}).json()
 assert data["priority"]=="high"
 assert data["detected_dates"]==["2030-12-15"]
 assert data["needs_confirmation"] is True
