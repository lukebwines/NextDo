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


def test_alert_scope_and_revocation(tmp_path):
 c,h=init(tmp_path);p="/api/work-mobile";m="/api/mobile/v1/work"
 a=c.post("/api/tasks",headers=h,json={"title":"Secret title","description":"Secret body","kind":"appointment","status":"review","priority":"critical","due_at":"2027-01-01"});assert a.status_code==200
 code=c.post(p+"/pair",headers=h).json()["code"]
 dev=c.post(m+"/pair",json={"code":code}).json()["device_token"]
 main={"Authorization":"Bearer "+dev}
 assert c.get(m+"/alerts",headers=main).status_code==401
 result=c.post(m+"/alerts/enable",headers=main)
 assert result.status_code==200,result.text
 alert={"Authorization":"Bearer "+result.json()["alert_token"]}
 result=c.get(m+"/alerts",headers=alert)
 assert result.status_code==200,result.text
 data=result.json()["items"]
 assert len(data)==1 and data[0]["review"] and data[0]["date_only"]
 assert set(data[0])=={"key","kind","priority","review","when","date_only","acknowledged"}
 assert "Secret" not in result.text
 assert c.get(m+"/agenda",headers=alert).status_code==401
 assert c.post(m+"/alerts/enable",headers=alert).status_code==401
 assert c.post(m+"/alerts/disable",headers=main).status_code==200
 assert c.get(m+"/alerts",headers=alert).status_code==401
 alert={"Authorization":"Bearer "+c.post(m+"/alerts/enable",headers=main).json()["alert_token"]}
 assert c.post(m+"/revoke",headers=main).status_code==200
 assert c.get(m+"/alerts",headers=alert).status_code==401
 c.close()


def test_ack_shared_per_user_revision(tmp_path):
 c,h=init(tmp_path);p="/api/work-mobile";m="/api/mobile/v1/work"
 other=create_user(c,h,"alice")
 t=c.post("/api/tasks",headers=h,json={"title":"Review","scope":"common","status":"review","priority":"critical"}).json()["id"]
 def device():
  code=c.post(p+"/pair",headers=h).json()["code"]
  dev={"Authorization":"Bearer "+c.post(m+"/pair",json={"code":code}).json()["device_token"]}
  alert={"Authorization":"Bearer "+c.post(m+"/alerts/enable",headers=dev).json()["alert_token"]}
  return dev,alert
 d,a=device();d2,a2=device()
 item=c.get(m+"/alerts",headers=a).json()["items"][0]
 assert not item["acknowledged"]
 assert c.post(m+"/alerts/ack",headers=a,json={"key":item["key"]}).status_code==200
 assert c.get(m+"/alerts",headers=a2).json()["items"][0]["acknowledged"]
 assert c.get("/api/tasks/"+str(t)).json()["work_acknowledged"]
 assert c.get("/api/tasks/"+str(t)).json()["status"]=="review"
 assert c.post(m+"/agenda/"+str(t)+"/ack",headers=d,json={"revision":"wrong"}).status_code==409
 sign_in(c,h,"alice");d3,a3=device()
 assert not c.get(m+"/alerts",headers=a3).json()["items"][0]["acknowledged"]
 current=c.get("/api/tasks/"+str(t)).json()
 assert c.post(p+"/ack/"+str(t),headers=h,json={"revision":current["work_revision"]}).status_code==200
 assert c.get(m+"/alerts",headers=a3).json()["items"][0]["acknowledged"]
 assert c.post(m+"/alerts/push/register",headers=a3,json={"token":"x"*50,"project_id":"test"}).status_code==409
 c.close()


def test_push_payload_and_config(tmp_path,monkeypatch):
 import json
 from app import work_push
 from cryptography.hazmat.primitives.asymmetric import rsa
 from cryptography.hazmat.primitives import serialization
 c,h=init(tmp_path);p="/api/work-mobile";m="/api/mobile/v1/work"
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()
 service={"type":"service_account","project_id":"nextdo-test","client_email":"push@nextdo-test.iam.gserviceaccount.com","private_key":key}
 android={"project_info":{"project_id":"nextdo-test","project_number":"123456789"},"client":[{"client_info":{"mobilesdk_app_id":"1:123456789:android:abcdef","android_client_info":{"package_name":"uk.archis.nextdoviaggi"}},"api_key":[{"current_key":"A"*39}]}]}
 assert c.post(p+"/push/config",headers=h,json={"service":service,"android":android}).status_code==200
 assert "PRIVATE" not in c.get(p+"/push/config").text
 assert (tmp_path/"work-push-private.json").stat().st_mode & 0o077 == 0
 code=c.post(p+"/pair",headers=h).json()["code"]
 dev={"Authorization":"Bearer "+c.post(m+"/pair",json={"code":code}).json()["device_token"]}
 alert={"Authorization":"Bearer "+c.post(m+"/alerts/enable",headers=dev).json()["alert_token"]}
 result=c.get(m+"/alerts/push/config",headers=alert)
 assert result.status_code==200 and "private_key" not in result.text
 assert c.get(m+"/alerts/push/config",headers=dev).status_code==401
 assert c.post(m+"/alerts/push/register",headers=alert,json={"token":"F"*100,"project_id":"nextdo-test"}).status_code==200
 captured={}
 def fake(url,body,headers):
  captured.update(url=url,payload=json.loads(body));return {"name":"synthetic"}
 monkeypatch.setattr(work_push,"request",fake)
 work_push.send("nextdo-test","fake-access","F"*100)
 assert captured["payload"]["message"]["data"]=={"nextdo":"work_refresh"}
 assert "notification" not in captured["payload"]["message"]
 assert c.post(p+"/push/disable",headers=h).status_code==200
 assert c.get(m+"/alerts/push/config",headers=alert).json()["config"] is None
 c.close()

def test_review_actions_web_mobile_permissions_and_stale_revision(tmp_path):
 c,h=init(tmp_path);p="/api/work-mobile";m="/api/mobile/v1/work"
 create_user(c,h,"reader")
 def create(title,**kw):
  r=c.post("/api/tasks",headers=h,json={"title":title,"status":"review","labels":["Da verificare","Test"],"description":"[DA VERIFICARE] Scadenza generata automaticamente, non convalidata.",**kw})
  assert r.status_code==200,r.text
  return r.json()["id"]
 def pair():
  code=c.post(p+"/pair",headers=h).json()["code"]
  return {"Authorization":"Bearer "+c.post(m+"/pair",json={"code":code}).json()["device_token"]}
 tid=create("Already resolved",kind="appointment")
 other=create("To confirm")
 shared=create("Shared review",scope="common")
 admin=pair()
 row=c.get(m+"/agenda/"+str(tid),headers=admin).json()
 assert row["can_confirm_review"] and row["can_complete_review"]
 assert c.post(m+"/agenda/"+str(tid)+"/review",headers=admin,json={"revision":"old","action":"complete"}).status_code==409
 assert c.post(m+"/agenda/"+str(tid)+"/ack",headers=admin,json={"revision":row["revision"]}).status_code==200
 assert c.get("/api/tasks/"+str(tid)).json()["status"]=="review"
 body={"revision":row["revision"],"action":"complete"}
 assert c.post(m+"/agenda/"+str(tid)+"/review",headers=admin,json=body).json()["status"]=="done"
 assert c.post(m+"/agenda/"+str(tid)+"/review",headers=admin,json=body).status_code==409
 detail=c.get("/api/tasks/"+str(tid)).json()
 assert detail["status"]=="done" and detail["due_at"] is None and detail["labels"]==["Test"]
 assert "Scadenza confermata manualmente" in detail["description"]
 assert tid not in [x["id"] for x in c.get(m+"/agenda",headers=admin).json()["items"]]
 rev=c.get("/api/tasks/"+str(other)).json()["work_revision"]
 assert c.post(p+"/review/"+str(other),headers=h,json={"revision":rev,"action":"confirm"}).json()["status"]=="todo"
 sign_in(c,h,"reader")
 reader=pair()
 row=c.get(m+"/agenda/"+str(shared),headers=reader).json()
 assert not row["can_confirm_review"] and not row["can_complete_review"]
 assert c.post(m+"/agenda/"+str(shared)+"/review",headers=reader,json={"revision":row["revision"],"action":"complete"}).status_code==403
 assert c.post(m+"/agenda/"+str(tid)+"/review",headers=reader,json=body).status_code==404
 c.close()

def test_review_complete_requires_explicit_form_confirmation_and_respects_per_course(tmp_path):
 c,h=init(tmp_path)
 def create(**kw):
  r=c.post("/api/tasks",headers=h,json={"title":"Synthetic review","status":"review",**kw})
  assert r.status_code==200,r.text
  return r.json()["id"]
 tid=create()
 url="/api/tasks/"+str(tid)
 row=c.get(url).json()
 payload={"title":"Synthetic review","status":"done","scope":"personal"}
 assert c.put(url,headers=h,json=payload).status_code==400
 assert c.put(url,headers=h,json={**payload,"confirm_review":True,"review_revision":"old"}).status_code==409
 assert c.put(url,headers=h,json={**payload,"confirm_review":True,"review_revision":row["work_revision"]}).status_code==200
 assert c.get(url).json()["status"]=="done"
 shared=create(scope="common",completion_mode="per_course")
 row=c.get("/api/tasks/"+str(shared)).json()
 assert row["can_confirm_review"] and not row["can_complete_review"]
 assert c.post("/api/work-mobile/review/"+str(shared),headers=h,json={"revision":row["work_revision"],"action":"complete"}).status_code==403
 assert c.get("/api/tasks/"+str(shared)).json()["status"]=="review"
 c.close()
