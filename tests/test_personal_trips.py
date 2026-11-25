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
