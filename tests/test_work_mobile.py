from test_workspace import init,create_user,sign_in
def test_work_agenda_pair_permissions(tmp_path):
 c,h=init(tmp_path);p="/api/work-mobile";m="/api/mobile/v1/work"
 alice=create_user(c,h,"alice")
 def task(title,**kw):
  r=c.post("/api/tasks",headers=h,json={"title":title,**kw});assert r.status_code==200,r.text;return r.json()["id"]
 private=task("Private administrator review",status="review",kind="appointment",due_at="2027-01-01")
 common=task("Shared deadline",scope="common",priority="critical")
 task("Private note",kind="note")
 task("Finished",status="done")
 def pair():
  code=c.post(p+"/pair",headers=h).json()["code"]
  result=c.post(m+"/pair",json={"code":code});assert result.status_code==200,result.text
  assert c.post(m+"/pair",json={"code":code}).status_code==401
  return {"Authorization":"Bearer "+result.json()["device_token"]}
 assert c.get(m+"/agenda").status_code==401
 admin=pair()
 items=c.get(m+"/agenda",headers=admin).json()["items"]
 assert {i["id"] for i in items}=={private,common}
 assert next(i for i in items if i["id"]==private)["day"]=="2027-01-01"
 assert next(i for i in items if i["id"]==private)["status"]=="review"
 assert c.get("/api/mobile/v1/trips",headers=admin).status_code==401
 # Travel token must not grant professional access.
 assert c.post("/api/personal/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 code=c.post("/api/personal/mobile/pair",headers=h).json()["code"]
 dev=c.post("/api/mobile/v1/pair",json={"code":code}).json()["device_token"]
 session=c.post("/api/mobile/v1/unlock",headers={"Authorization":"Bearer "+dev},json={"pin":"123456"}).json()["session_token"]
 assert c.get(m+"/agenda",headers={"Authorization":"Bearer "+session}).status_code==401
 sign_in(c,h,"alice")
 other=pair()
 assert {i["id"] for i in c.get(m+"/agenda",headers=other).json()["items"]}=={common}
 assert c.get(m+"/agenda/"+str(private),headers=other).status_code==404
 assert c.get(m+"/agenda/"+str(common),headers=other).status_code==200
 did=c.get(p+"/devices").json()[0]["id"]
 assert c.post(p+"/devices/"+did+"/revoke",headers=h).status_code==200
 assert c.get(m+"/agenda",headers=other).status_code==401
 assert c.post(m+"/revoke",headers=admin).status_code==200
 assert c.get(m+"/agenda",headers=admin).status_code==401
 c.close()
