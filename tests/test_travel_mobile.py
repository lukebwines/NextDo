import time
from test_workspace import init,create_user,sign_in
from test_personal_trips import sample

def test_mobile_scoped_pair_pin_revoke(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/mobile/pair",headers=h).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 pair=c.post(mobile+"/pair",json={"code":code,"label":"Synthetic Android"});assert pair.status_code==200,pair.text
 assert c.post(mobile+"/pair",json={"code":code}).status_code==401
 d=pair.json()
 assert d["device_token"] not in str(c.get(p+"/mobile/devices").json())
 device={"Authorization":"Bearer "+d["device_token"]}
 assert c.get(mobile+"/trips",headers=device).status_code==401
 assert c.post(mobile+"/unlock",headers=device,json={"pin":"000000"}).status_code==403
 r=c.post(mobile+"/unlock",headers=device,json={"pin":"123456"});assert r.status_code==200,r.text
 session={"Authorization":"Bearer "+r.json()["session_token"]}
 c.cookies.delete("nextdo_session")
 assert c.get("/api/tasks",headers=session).status_code==401
 assert c.get(p+"/trips",headers=session).status_code==401
 assert c.get(mobile+"/trips",headers=session).json()[0]["id"]==m["trip"]["id"]
 url=mobile+"/trips/"+m["trip"]["id"]
 assert c.get(url,headers=session).json()["manifest"]==m
 assert c.get(url+"/offline",headers=session).status_code==200
 assert c.get(url+"/documents/test.pdf",headers=session).content==b"%PDF-synthetic"
 assert c.get(url+"/missing",headers=session).status_code==404
 sign_in(c,h,"admin")
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 assert c.post(p+"/mobile/devices/"+d["device_id"]+"/revoke",headers=h).status_code==200
 assert c.get(url,headers=session).status_code==401
 assert c.post(mobile+"/unlock",headers=device,json={"pin":"123456"}).status_code==401
 c.close()


def test_trusted_device_requires_first_pin_and_revokes(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 def pair():
  code=c.post(p+"/mobile/pair",headers=h).json()["code"]
  return c.post(mobile+"/pair",json={"code":code}).json()
 d=pair();other=pair()
 device={"Authorization":"Bearer "+d["device_token"]}
 another={"Authorization":"Bearer "+other["device_token"]}
 assert c.post(mobile+"/resume",headers=device,json={"remember_token":"x"*43}).status_code==401
 assert c.post(mobile+"/unlock",headers=device,json={"pin":"000000","remember":True}).status_code==403
 r=c.post(mobile+"/unlock",headers=device,json={"pin":"123456","remember":True})
 assert r.status_code==200,r.text
 saved=r.json()["remember_token"]
 assert saved not in str(c.get(p+"/mobile/devices").json())
 assert c.post(mobile+"/resume",headers=another,json={"remember_token":saved}).status_code==401
 old={"Authorization":"Bearer "+r.json()["session_token"]}
 assert c.post(mobile+"/lock",headers=old).status_code==200
 resumed=c.post(mobile+"/resume",headers=device,json={"remember_token":saved})
 assert resumed.status_code==200,resumed.text
 session={"Authorization":"Bearer "+resumed.json()["session_token"]}
 assert c.get(mobile+"/trips",headers=session).status_code==200
 assert c.post(p+"/mobile/devices/"+d["device_id"]+"/revoke",headers=h).status_code==200
 assert c.post(mobile+"/resume",headers=device,json={"remember_token":saved}).status_code==401
 assert c.get(mobile+"/trips",headers=session).status_code==401
 c.close()
