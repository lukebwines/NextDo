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

def test_offline_snapshot_tracks_pdf_and_timeline_and_auth(tmp_path):
 import hashlib,io,zipfile
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 device={"Authorization":"Bearer "+d["device_token"]}
 s={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers=device,json={"pin":"123456"}).json()["session_token"]}
 tid=m["trip"]["id"];url=mobile+"/trips/"+tid;web=p+"/trips/"+tid
 assert c.get(url+"/offline-state",headers=device).status_code==401
 def state():return c.get(url+"/offline-state",headers=s).json()
 def download(expected):
  r=c.get(url+"/offline?include_timeline=true",headers=s)
  assert r.status_code==200,r.text
  assert r.headers["X-NextDo-Snapshot"]==expected["snapshot"]
  assert r.headers["X-NextDo-Archive-SHA256"]==hashlib.sha256(r.content).hexdigest()
  assert int(r.headers["X-NextDo-Revision"])==expected["revision"]
  return zipfile.ZipFile(io.BytesIO(r.content))
 initial=state();assert initial==state()
 with download(initial) as z:assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
 r=c.post(web+"/documents/test.pdf/replace?revision="+str(initial["revision"])+"&confirm_shared=true",headers=h,files={"file":("test.pdf",b"%PDF-updated","application/pdf")})
 assert r.status_code==200,r.text
 changed=state()
 assert changed["snapshot"]!=initial["snapshot"] and changed["revision"]>initial["revision"]
 with download(changed) as z:assert z.read("documenti/test.pdf")==b"%PDF-updated"
 timeline={"from":"2027-01-01","to":"2027-01-01","visits":[{"startTime":"2027-01-01T10:00:00+01:00","endTime":"2027-01-01T10:01:00+01:00","location":{"lat":1,"lon":2}}],"activities":[],"paths":[]}
 assert c.post(url+"/timeline",headers=s,json=timeline).status_code==200
 diary=state();assert diary["snapshot"]!=changed["snapshot"] and diary["revision"]==changed["revision"]
 with download(diary) as z:assert "timeline.json" in z.namelist()
 assert c.post(web+"/timeline/clear",headers=h).status_code==200
 assert state()==changed
 assert c.post(p+"/mobile/devices/"+d["device_id"]+"/revoke",headers=h).status_code==200
 assert c.get(url+"/offline-state",headers=s).status_code==401
 c.close()

def test_mobile_dynamic_templates_and_offline_catalog(tmp_path):
 import io,json,zipfile
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 def pair(pin):
  code=c.post(p+"/mobile/pair",headers=h).json()["code"]
  d=c.post(mobile+"/pair",json={"code":code}).json()
  device={"Authorization":"Bearer "+d["device_token"]}
  s={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers=device,json={"pin":pin}).json()["session_token"]}
  return device,s
 device,s=pair("123456")
 assert c.get(mobile+"/booking-templates",headers=device).status_code==401
 url=mobile+"/trips/"+m["trip"]["id"]
 old=c.get(url+"/offline-state",headers=s).json()
 start=c.get(url+"/offline-state?include_catalog=true",headers=s).json()
 model={"label":"Synthetic shuttle","icon":"car","fields":["Pick-up","Code"],"roles":["Terminal"]}
 r=c.post(p+"/booking-templates",headers=h,json=model);assert r.status_code==200,r.text
 custom=next(t for t in r.json() if t["label"]==model["label"]);ident=custom["id"]
 assert custom in c.get(mobile+"/booking-templates",headers=s).json()["templates"]
 assert custom in c.get(url,headers=s).json()["templates"]
 changed=c.get(url+"/offline-state?include_catalog=true",headers=s).json()
 assert changed["snapshot"]!=start["snapshot"] and changed["revision"]==start["revision"]
 assert c.get(url+"/offline-state",headers=s).json()==old
 r=c.get(url+"/offline?include_timeline=true&include_catalog=true",headers=s)
 assert r.status_code==200 and r.headers["X-NextDo-Snapshot"]==changed["snapshot"]
 with zipfile.ZipFile(io.BytesIO(r.content)) as z:
  assert custom in json.loads(z.read("booking-templates.json"))
  assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
 with zipfile.ZipFile(io.BytesIO(c.get(url+"/offline?include_timeline=true",headers=s).content)) as z:
  assert "booking-templates.json" not in z.namelist()
 payload={"revision":0,"kind":"booking","id":"hotel-test","fields":{"title":"Synthetic shuttle booking"},"template_id":ident,"specific_fields":[["Pick-up","Terminal A"],["Code","X"],["Legacy field","Keep"]]}
 r=c.post(url+"/edit",headers=s,json=payload);assert r.status_code==200,r.text
 saved=r.json()["manifest"]["bookings"][0]
 assert saved["kind"]==ident and saved["template_icon"]=="car" and saved["template_label"]==model["label"]
 assert saved["doc"]=="test.pdf" and saved["lines"]==m["bookings"][0]["lines"] and saved["fields"]==payload["specific_fields"]
 create_user(c,h,"catalog_other");sign_in(c,h,"catalog_other")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 _,other=pair("654321")
 assert ident not in [t["id"] for t in c.get(mobile+"/booking-templates",headers=other).json()["templates"]]
 assert c.get(url+"/offline?include_catalog=true",headers=other).status_code==404
 sign_in(c,h,"admin")
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 assert c.delete(p+"/booking-templates/"+ident,headers=h).status_code==200
 assert c.post(url+"/edit",headers=s,json={**payload,"revision":1}).status_code==409
 r=c.post(url+"/edit",headers=s,json={"revision":1,"kind":"booking","id":"hotel-test","fields":{"title":"Historical booking"},"specific_fields":saved["fields"]});assert r.status_code==200,r.text
 historical=r.json()["manifest"]["bookings"][0]
 assert historical["kind"]==ident and historical["template_label"]==saved["template_label"] and historical["fields"]==saved["fields"]
 assert c.post(url+"/edit",headers=s,json={"revision":2,"kind":"booking","id":"hotel-test","fields":{"title":"Bad"},"specific_fields":[["","new"]]}).status_code==400
 c.close()

def test_mobile_budget_and_expenses(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 s={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers={"Authorization":"Bearer "+d["device_token"]},json={"pin":"123456"}).json()["session_token"]}
 raw,m=sample()
 assert c.post(mobile+"/trips/import",headers={**s,"Content-Type":"application/zip"},content=raw).status_code==200
 url=mobile+"/trips/"+m["trip"]["id"]
 def edit(rev,kind,fields,**kw):return c.post(url+"/edit",headers=s,json={"revision":rev,"kind":kind,"fields":fields,**kw})
 assert edit(0,"budget",{"amount":"3000,00","currency":"eur"}).status_code==200
 assert edit(1,"expense",{"title":"Hotel","amount":"200.00","currency":"USD","status":"Pagata","base_amount":"185.00","base_currency":"EUR","booking_id":"hotel-test","doc":"test.pdf"}).status_code==200
 assert edit(2,"expense",{"title":"Invalid","amount":"-1","currency":"USD"}).status_code==400
 assert edit(2,"expense",{"title":"Invalid","amount":"10","currency":"USD","booking_id":"absent"}).status_code==400
 assert edit(1,"expense",{"status":"Da sostenere"},index=0).status_code==409
 assert edit(2,"expense",{"status":"Da sostenere"},index=0).status_code==200
 result=c.get(url,headers=s).json()["manifest"]
 assert result["budget"]=={"amount":"3000.00","currency":"EUR"}
 assert result["expenses"][0]["status"]=="Da sostenere"
 assert result["expenses"][0]["doc"]=="test.pdf"
 assert c.get(p+"/trips/"+m["trip"]["id"],headers=h).json()["manifest"]==result
 assert c.get(url+"/offline",headers=s).status_code==200
 c.close()

def test_budget_delete_conversion_and_receipt(tmp_path,monkeypatch):
 from app import personal_travel_tools as tools
 import base64,io
 from PIL import Image
 monkeypatch.setattr(tools,"exchange_rates",lambda:{"date":"2026-11-25","rates":{"EUR":"1","USD":"1.25"},"source":"BCE"})
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 s={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers={"Authorization":"Bearer "+d["device_token"]},json={"pin":"123456"}).json()["session_token"]}
 raw,m=sample()
 assert c.post(mobile+"/trips/import",headers={**s,"Content-Type":"application/zip"},content=raw).status_code==200
 url=mobile+"/trips/"+m["trip"]["id"]
 def edit(rev,kind,fields):return c.post(url+"/edit",headers=s,json={"revision":rev,"kind":kind,"fields":fields})
 assert edit(0,"budget",{"amount":"1000","currency":"EUR"}).status_code==200
 assert edit(1,"expense",{"title":"Test","amount":"25","currency":"USD"}).status_code==200
 r=c.post(url+"/expenses/convert",headers=s,json={"revision":2});assert r.status_code==200,r.text
 assert r.json()["manifest"]["expenses"][0]["base_amount"]=="20.00"
 assert r.json()["manifest"]["expenses"][0]["fx_date"]=="2026-11-25"
 assert c.post(url+"/expenses/convert",headers=s,json={"revision":3}).json()["revision"]==3
 img=io.BytesIO();Image.new("RGB",(20,30),"white").save(img,format="PNG")
 r=c.post(url+"/expenses/receipt",headers=s,json={"revision":3,"index":0,"content":base64.b64encode(img.getvalue()).decode()});assert r.status_code==200,r.text
 name=r.json()["manifest"]["expenses"][0]["doc"]
 assert c.get(url+"/documents/"+name,headers=s).content.startswith(b"%PDF-")
 assert c.post(url+"/expenses/delete",headers=s,json={"revision":3,"index":0}).status_code==409
 r=c.post(url+"/expenses/delete",headers=s,json={"revision":4,"index":0});assert r.status_code==200,r.text
 assert r.json()["manifest"]["expenses"]==[]
 assert c.get(url+"/documents/"+name,headers=s).status_code==200
 c.close()

def test_offline_expense_queue_idempotency(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 s={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers={"Authorization":"Bearer "+d["device_token"]},json={"pin":"123456"}).json()["session_token"]}
 raw,m=sample()
 assert c.post(mobile+"/trips/import",headers={**s,"Content-Type":"application/zip"},content=raw).status_code==200
 url=mobile+"/trips/"+m["trip"]["id"]
 body={"entries":[{"id":"a"*32,"fields":{"title":"Taxi","amount":"12,50","currency":"usd","status":"Pagata"}}]}
 r=c.post(url+"/expenses/sync",headers=s,json=body);assert r.status_code==200,r.text
 assert r.json()["revision"]==1 and len(r.json()["manifest"]["expenses"])==1
 r=c.post(url+"/expenses/sync",headers=s,json=body);assert r.json()["revision"]==1
 assert c.post(url+"/expenses/delete",headers=s,json={"revision":1,"index":0}).status_code==200
 r=c.post(url+"/expenses/sync",headers=s,json=body);assert r.json()["revision"]==2 and r.json()["manifest"]["expenses"]==[]
 assert c.post(url+"/expenses/sync",headers=s,json={"entries":[{"id":"b"*32,"fields":{"title":"Bad","amount":"-1","currency":"EUR"}}]}).status_code==400
 c.close()
