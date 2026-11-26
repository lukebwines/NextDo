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


def test_mobile_import_create_edit(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 def pair(pin):
  code=c.post(p+"/mobile/pair",headers=h).json()["code"]
  d=c.post(mobile+"/pair",json={"code":code}).json()
  dev={"Authorization":"Bearer "+d["device_token"]}
  s=c.post(mobile+"/unlock",headers=dev,json={"pin":pin}).json()["session_token"]
  return dev,{"Authorization":"Bearer "+s}
 dev,s=pair("123456");raw,m=sample()
 z={**s,"Content-Type":"application/zip"}
 assert c.post(mobile+"/trips/import",headers=dev,content=raw).status_code==401
 assert c.post(mobile+"/trips/import",headers=z,content=b"not a zip").status_code==400
 imported=c.post(mobile+"/trips/import",headers=z,content=raw)
 assert imported.status_code==200,imported.text
 assert c.post(mobile+"/trips/import",headers=z,content=raw).status_code==409
 url=mobile+"/trips/"+m["trip"]["id"]
 def edit(rev,kind,fields,**kwargs):return c.post(url+"/edit",headers=s,json={"revision":rev,"kind":kind,"fields":fields,**kwargs})
 assert edit(0,"day",{"headline":"New day"},date="2027-01-01").status_code==200
 assert edit(0,"day",{"headline":"Stale"},date="2027-01-01").status_code==409
 assert edit(1,"event",{"title":"Updated"},date="2027-01-01",index=0).status_code==200
 assert edit(2,"booking",{"title":"New hotel"},id="hotel-test").status_code==200
 assert edit(3,"booking",{"title":"New booking","type":"Other"}).status_code==200
 assert edit(4,"booking",{"doc":"missing.pdf"},id="hotel-test").status_code==400
 assert edit(4,"event",{"title":"Added"},date="2027-01-01").status_code==200
 assert edit(5,"trip",{"title":"Renamed"}).status_code==200
 updated=c.get(url,headers=s).json()
 assert updated["manifest"]["days"][0]["events"][0]["bid"]=="hotel-test"
 assert updated["manifest"]["bookings"][0]["doc"]=="test.pdf"
 assert updated["state"]["notes"]["2027-01-01"]=="Test note"
 assert c.get(url+"/documents/test.pdf",headers=s).content==b"%PDF-synthetic"
 new=c.post(mobile+"/trips",headers=s,json={"title":"New","start":"2027-02-01","end":"2027-02-03"})
 assert new.status_code==200,new.text
 assert len(c.get(mobile+"/trips/"+new.json()["id"],headers=s).json()["manifest"]["days"])==3
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 _,other=pair("654321")
 assert c.post(url+"/edit",headers=other,json={"revision":6,"kind":"trip","fields":{"title":"Other"}}).status_code==404
 assert c.get(mobile+"/trips",headers=other).json()==[]
 c.close()

def test_mobile_pin_accepts_custom_four_digit_pin(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"4321","confirm":"4321"}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 paired=c.post(mobile+"/pair",json={"code":code,"label":"Four digit test"})
 assert paired.status_code==200,paired.text
 device={"Authorization":"Bearer "+paired.json()["device_token"]}
 assert c.post(mobile+"/unlock",headers=device,json={"pin":"123456"}).status_code==403
 unlocked=c.post(mobile+"/unlock",headers=device,json={"pin":"4321"})
 assert unlocked.status_code==200,unlocked.text
 c.close()
