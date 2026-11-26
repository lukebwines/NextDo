"""Synthetic private-trip tests: never use real bookings in Git."""
import io,json,zipfile
from test_workspace import init,create_user,sign_in

def sample():
 m={"format_version":1,"trip":{"id":"synthetic-trip","title":"Private synthetic trip","start":"2027-01-01","end":"2027-01-02"},"bookings":[{"id":"hotel-test","title":"Synthetic hotel","doc":"test.pdf","map":"https://example.org/maps","lines":[["Check-in","15:00"]]}],"days":[{"date":"2027-01-01","events":[{"title":"Hotel","bid":"hotel-test","gid":"guide-test"}],"checks":["Test checklist"]}],"guides":[{"id":"guide-test","title":"Synthetic guide","doc":"test.pdf","items":[["Test","Info"]],"links":[{"label":"Map","url":"https://example.org"}]}],"documents":[]}
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:
  z.writestr("manifest.json",json.dumps(m));z.writestr("documenti/test.pdf",b"%PDF-synthetic");z.writestr("notes.json",json.dumps({"revision":0,"notes":{"2027-01-01":"Test note"},"checks":{"2027-01-01":[0]}}))
 return b.getvalue(),m

def test_import_owner_pin_export(tmp_path):
 c,h=init(tmp_path)
 p="/api/personal"
 assert c.get(p+"/trips").status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 r=c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")})
 assert r.status_code==200,r.text
 tid=r.json()["id"];url=p+"/trips/"+tid
 assert c.get(url).json()["manifest"]==m
 assert c.get(url).json()["state"]["checks"]=={"2027-01-01":[0]}
 assert c.get(url+"/documents/test.pdf").content==b"%PDF-synthetic"
 assert c.get(url+"/export").headers["cache-control"]=="no-store, private"
 assert c.get("/api/tasks").json()==[]
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==409
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.get(url+"/documents/test.pdf").status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"000000"}).status_code==403
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.get(url).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert c.get(url).status_code==404
 assert c.get(p+"/trips").json()==[]
 c.close()

def test_create_and_edit(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 r=c.post(p+"/trips",headers=h,json={"title":"New synthetic trip","start":"2027-01-01","end":"2027-01-02"})
 assert r.status_code==200,r.text
 url=p+"/trips/"+r.json()["id"];b=c.get(url).json()
 assert len(b["manifest"]["days"])==2
 b["manifest"]["days"][0]["headline"]="New plan"
 assert c.put(url,headers=h,json=b).status_code==200
 assert c.put(url,headers=h,json=b).status_code==409
 assert c.get(url).json()["manifest"]["days"][0]["headline"]=="New plan"
 c.close()

def test_private_cover_image(tmp_path):
 from PIL import Image
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 r=c.post(p+"/trips",headers=h,json={"title":"Synthetic cover trip","start":"2027-01-01","end":"2027-01-02"})
 url=p+"/trips/"+r.json()["id"]
 assert c.get(url+"/cover-image").status_code==404
 buf=io.BytesIO();Image.new("RGB",(32,20),"teal").save(buf,format="PNG")
 assert c.post(url+"/cover",headers=h,files={"file":("cover.png",buf.getvalue(),"image/png")}).status_code==200
 result=c.get(url+"/cover-image")
 assert result.status_code==200 and result.headers["content-type"]=="image/jpeg"
 assert result.headers["cache-control"]=="no-store, private"
 assert result.content.startswith(b"\xff\xd8")
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.get(url+"/cover-image").status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert c.get(url+"/cover-image").status_code==404
 c.close()

def test_booking_templates_private_reusable(tmp_path):
 c,h=init(tmp_path);p="/api/personal";url=p+"/booking-templates"
 assert c.get(url).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 catalog=c.get(url).json()
 assert {"insurance","parking","esim"}<={t["id"] for t in catalog}
 data={"label":"Synthetic transfer","icon":"car","fields":["Booking number","Pickup"],"roles":["Pickup"]}
 r=c.post(url,headers=h,json=data);assert r.status_code==200,r.text
 t=next(x for x in r.json() if x["label"]==data["label"]);tid=t["id"]
 assert c.post(url,headers=h,json={**t,"fields":["Code","code"]}).status_code==400
 assert c.post(url,headers=h,json={**t,"fields":["Code"]}).status_code==200
 trip=c.post(p+"/trips",headers=h,json={"title":"Synthetic trip","start":"2027-01-01","end":"2027-01-02"}).json()["id"]
 trip_url=p+"/trips/"+trip;b=c.get(trip_url).json()
 b["manifest"]["bookings"].append({"id":"booking-example","title":"Synthetic booking","kind":tid,"type":t["label"],"template_label":t["label"],"template_icon":t["icon"],"fields":[["Code","123"]],"lines":[]})
 assert c.put(trip_url,headers=h,json=b).status_code==200
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.get(url).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 assert any(x["id"]==tid for x in c.get(url).json())
 assert c.delete(url+"/"+tid,headers=h).status_code==200
 assert c.get(trip_url).json()["manifest"]["bookings"][0]["fields"]==[["Code","123"]]
 c.post(url,headers=h,json=data)
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert all(x["label"]!=data["label"] for x in c.get(url).json())
 c.close()

def test_replace_pdf_keeps_links_and_refreshes_mobile(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 tid=m["trip"]["id"];url=p+"/trips/"+tid;mu=mobile+"/trips/"+tid
 b=c.get(url).json()
 b["manifest"]["documents"].append({"file":"test.pdf","title":"test.pdf"})
 b["manifest"]["expenses"]=[{"title":"Synthetic expense","amount":"10","currency":"EUR","doc":"test.pdf"}]
 assert c.put(url,headers=h,json=b).status_code==200
 assert c.post(url+"/documents",headers=h,files={"file":("collision.pdf",b"%PDF-other","application/pdf")}).status_code==200
 before=c.get(url).json();rev=before["revision"]
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 device={"Authorization":"Bearer "+d["device_token"]}
 session={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers=device,json={"pin":"123456"}).json()["session_token"]}
 def replace(name,content,revision=rev,shared=True):
  return c.post(url+"/documents/test.pdf/replace",params={"revision":revision,"confirm_shared":shared,"original":True},headers=h,files={"file":(name,content,"application/pdf")})
 assert replace("original.pdf",b"%PDF-original",shared=False).status_code==409
 assert replace("original.pdf",b"%PDF-original",revision=rev-1).status_code==409
 assert replace("collision.pdf",b"%PDF-original").status_code==409
 assert replace("original.pdf",b"not pdf").status_code==400
 assert c.get(url).json()==before
 assert c.get(mu+"/documents/test.pdf",headers=session).content==b"%PDF-synthetic"
 r=replace("original.pdf",b"%PDF-original");assert r.status_code==200,r.text
 assert r.json()=={"revision":rev+1,"file":"original.pdf","linked":3}
 after=c.get(mu,headers=session).json()
 assert after["revision"]==rev+1
 assert after["state"]==before["state"]
 assert after["manifest"]["days"]==before["manifest"]["days"]
 assert after["manifest"]["bookings"][0]["doc"]=="original.pdf"
 assert after["manifest"]["bookings"][0]["original"] is True
 assert after["manifest"]["bookings"][0]["lines"]==before["manifest"]["bookings"][0]["lines"]
 assert after["manifest"]["guides"][0]["doc"]=="original.pdf"
 assert after["manifest"]["expenses"][0]["doc"]=="original.pdf"
 assert after["manifest"]["documents"][0]=={"file":"original.pdf","title":"original.pdf"}
 assert c.get(mu+"/documents/test.pdf",headers=session).status_code==404
 assert c.get(mu+"/documents/original.pdf",headers=session).content==b"%PDF-original"
 snapshot=c.get(mu+"/offline",headers=session)
 with zipfile.ZipFile(io.BytesIO(snapshot.content)) as z:
  assert "documenti/test.pdf" not in z.namelist()
  assert z.read("documenti/original.pdf")==b"%PDF-original"
  assert z.read("documenti/collision.pdf")==b"%PDF-other"
 assert c.post(url+"/documents/original.pdf/replace",params={"revision":rev+1,"confirm_shared":True},headers=h,files={"file":("original.pdf",b"%PDF-same-name","application/pdf")}).status_code==200
 assert c.get(mu+"/documents/original.pdf",headers=session).content==b"%PDF-same-name"
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(url+"/documents/original.pdf/replace",params={"revision":rev+2},headers=h,files={"file":("original.pdf",b"%PDF-locked","application/pdf")}).status_code==423
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert c.post(url+"/documents/original.pdf/replace",params={"revision":rev+2},headers=h,files={"file":("original.pdf",b"%PDF-other-account","application/pdf")}).status_code==404
 c.close()

def test_multiple_booking_documents(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 tid=m["trip"]["id"];url=p+"/trips/"+tid
 assert c.post(url+"/documents",headers=h,files={"file":("voucher.pdf",b"%PDF-voucher","application/pdf")}).status_code==200
 b=c.get(url).json()
 booking=b["manifest"]["bookings"][0]
 booking["doc_label"]="Riepilogo integrativo"
 booking["attachments"]=[{"file":"voucher.pdf","label":"Conferma originale"}]
 assert c.put(url,headers=h,json=b).status_code==200
 assert c.get(url).json()["manifest"]["bookings"][0]["doc"]=="test.pdf"
 assert c.get(url+"/documents/test.pdf").content==b"%PDF-synthetic"
 latest=c.get(url).json()
 latest["manifest"]["bookings"][0]["attachments"].append({"file":"test.pdf","label":"Duplicato"})
 assert c.put(url,headers=h,json=latest).status_code==400
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 dev={"Authorization":"Bearer "+d["device_token"]}
 session={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers=dev,json={"pin":"123456"}).json()["session_token"]}
 mu=mobile+"/trips/"+tid
 assert c.get(mu,headers=session).json()["manifest"]["bookings"][0]["attachments"]==[{"file":"voucher.pdf","label":"Conferma originale"}]
 assert c.get(mu+"/documents/voucher.pdf",headers=session).content==b"%PDF-voucher"
 with zipfile.ZipFile(io.BytesIO(c.get(mu+"/offline",headers=session).content)) as z:
  assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
  assert z.read("documenti/voucher.pdf")==b"%PDF-voucher"
 rev=c.get(url).json()["revision"]
 r=c.post(url+"/documents/voucher.pdf/replace",params={"revision":rev},headers=h,files={"file":("new.pdf",b"%PDF-new","application/pdf")})
 assert r.status_code==200,r.text
 assert c.get(mu,headers=session).json()["manifest"]["bookings"][0]["attachments"]==[{"file":"new.pdf","label":"Conferma originale"}]
 x=c.get(url).json();x["manifest"]["bookings"][0]["attachments"]=[]
 assert c.put(url,headers=h,json=x).status_code==200
 assert c.get(url+"/documents/new.pdf").content==b"%PDF-new"
 c.close()

def test_personal_appearance_private_and_validated(tmp_path):
 from PIL import Image
 c,h=init(tmp_path);p="/api/personal";url=p+"/appearance"
 assert c.get(url).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.get(url).json()=={"theme":"dark","palette":"ocean","background":"gradient","photo":None}
 pref={"theme":"light","palette":"forest","background":"plain"}
 assert c.post(url,headers=h,json=pref).json()=={**pref,"photo":None}
 assert c.post(url,headers=h,json={"palette":"bad"}).status_code==400
 assert c.post(url,headers=h,json={"background":"photo"}).status_code==400
 buf=io.BytesIO();Image.new("RGB",(32,20),"teal").save(buf,format="PNG")
 assert c.post(url+"/photo",headers=h,files={"file":("private.png",buf.getvalue(),"image/png")}).status_code==200
 assert c.get(url).json()["background"]=="photo"
 assert c.get(url).json()["photo"]
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.get(url).status_code==423
 assert c.get("/api/mobile/v1/appearance").status_code==401
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(url,headers=h,json={"clear_photo":True}).json()["photo"] is None
 assert c.get(url).json()["background"]=="gradient"
 create_user(c,h,"appearance-colleague");sign_in(c,h,"appearance-colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert c.get(url).json()["theme"]=="dark"
 c.close()

def test_private_items_are_not_professional_or_shared(tmp_path):
 c,h=init(tmp_path);p="/api/personal";url=p+"/items"
 assert c.get(url).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 r=c.post(url,headers=h,json={"title":"Synthetic private item","kind":"deadline","due_at":"2027-01-01"})
 assert r.status_code==200,r.text
 i=r.json()["id"]
 assert c.get(url).json()["items"][0]["title"]=="Synthetic private item"
 assert c.get("/api/tasks").json()==[]
 assert c.post(url+"/"+str(i),headers=h,json={"status":"done"}).status_code==200
 assert c.get("/api/mobile/v1/items").status_code==401
 create_user(c,h,"private-items-colleague");sign_in(c,h,"private-items-colleague")
 assert c.post(p+"/unlock",headers=h,json={"pin":"654321","confirm":"654321"}).status_code==200
 assert c.get(url).json()["items"]==[]
 assert c.post(url+"/"+str(i),headers=h,json={"title":"Unauthorized"}).status_code==404
 c.close()

def test_private_transfer_manual_roundtrip(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 i=c.post(p+"/items",headers=h,json={"title":"Synthetic move","kind":"deadline","due_at":"2027-01-03"}).json()["id"]
 assert c.post(p+"/transfers",headers=h,json={"action":"to_work","id":i}).status_code==400
 r=c.post(p+"/transfers",headers=h,json={"action":"to_work","id":i,"confirm":True});assert r.status_code==200,r.text
 tid=r.json()["id"]
 assert c.get(p+"/items").json()["items"]==[]
 assert c.get("/api/tasks").json()[0]["title"]=="Synthetic move"
 r=c.post(p+"/transfers",headers=h,json={"action":"to_private","id":tid,"confirm":True});assert r.status_code==200,r.text
 assert c.get("/api/tasks").json()==[]
 assert c.get(p+"/items").json()["items"][0]["kind"]=="deadline"
 c.close()

def test_private_alert_token_is_metadata_only(tmp_path):
 c,h=init(tmp_path);p="/api/personal";mobile="/api/mobile/v1"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(p+"/items",headers=h,json={"title":"Secret synthetic item","description":"Secret details","status":"review"}).status_code==200
 code=c.post(p+"/mobile/pair",headers=h).json()["code"]
 d=c.post(mobile+"/pair",json={"code":code}).json()
 dev={"Authorization":"Bearer "+d["device_token"]}
 session={"Authorization":"Bearer "+c.post(mobile+"/unlock",headers=dev,json={"pin":"123456"}).json()["session_token"]}
 assert c.get(mobile+"/private-alerts",headers=session).status_code==401
 result=c.post(mobile+"/private-alerts/enable",headers=session).json()
 alert={"Authorization":"Bearer "+result["token"]}
 r=c.get(mobile+"/private-alerts",headers=alert)
 assert r.status_code==200,r.text
 assert len(r.json()["items"])==1 and set(r.json()["items"][0])=={"key"}
 assert "Secret" not in r.text
 assert c.get(mobile+"/items",headers=alert).status_code==401
 assert c.post(mobile+"/private-alerts/disable",headers=session).status_code==200
 assert c.get(mobile+"/private-alerts",headers=alert).status_code==401
 c.close()

def test_private_keepalive_requires_existing_unlock_and_respects_lock(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/keepalive",headers=h).status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(p+"/keepalive",headers=h).json()=={"unlocked":True}
 assert c.get(p+"/trips").status_code==200
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(p+"/keepalive",headers=h).status_code==423
 assert c.get(p+"/trips").status_code==423
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456"}).status_code==200
 assert c.post(p+"/keepalive",headers=h).status_code==200
 c.close()

def test_personal_pin_accepts_four_to_twelve_digits_and_can_be_changed(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123","confirm":"123"}).status_code==400
 assert c.get(p+"/status").json()["configured"] is False
 assert c.post(p+"/unlock",headers=h,json={"pin":"1234","confirm":"123"}).status_code==400
 assert c.post(p+"/unlock",headers=h,json={"pin":"1234","confirm":"1234"}).status_code==200
 assert c.post(p+"/change-pin",headers=h,json={"current_pin":"0000","new_pin":"123456789012","confirm":"123456789012"}).status_code==403
 assert c.post(p+"/change-pin",headers=h,json={"current_pin":"1234","new_pin":"1234567890123","confirm":"1234567890123"}).status_code==400
 assert c.post(p+"/change-pin",headers=h,json={"current_pin":"1234","new_pin":"123456789012","confirm":"12345678901"}).status_code==400
 assert c.post(p+"/change-pin",headers=h,json={"current_pin":"1234","new_pin":"1234","confirm":"1234"}).status_code==400
 changed=c.post(p+"/change-pin",headers=h,json={"current_pin":"1234","new_pin":"123456789012","confirm":"123456789012"})
 assert changed.status_code==200,changed.text
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(p+"/unlock",headers=h,json={"pin":"1234"}).status_code==403
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456789012"}).status_code==200
 changed=c.post(p+"/change-pin",headers=h,json={"current_pin":"123456789012","new_pin":"5678","confirm":"5678"})
 assert changed.status_code==200,changed.text
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(p+"/unlock",headers=h,json={"pin":"5678"}).status_code==200
 c.close()

def test_private_review_can_be_closed_without_inventing_date(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 url=p+"/items"
 item=c.post(url,headers=h,json={"title":"Resolved email","kind":"appointment","status":"review"})
 assert item.status_code==200,item.text
 target=url+"/"+str(item.json()["id"])
 assert c.post(target,headers=h,json={"status":"todo"}).status_code==400
 assert c.post(target,headers=h,json={"status":"done"}).status_code==200
 row=c.get(url).json()["items"][0]
 assert row["status"]=="done" and row["due_at"] is None
 assert c.post(url,headers=h,json={"title":"New","kind":"deadline","status":"done"}).status_code==400
 c.close()
