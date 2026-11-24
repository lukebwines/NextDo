import io,json,zipfile
from test_workspace import init
from test_personal_trips import sample
from PIL import Image
from app import personal_travel_tools as tools

def test_photo_expense_roundtrip(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 url=p+"/trips/"+m["trip"]["id"]
 img=io.BytesIO();Image.new("RGB",(300,200),"navy").save(img,"PNG")
 assert c.post(url+"/cover",headers=h,files={"file":("photo.png",img.getvalue(),"image/png")}).status_code==200
 b=c.get(url).json();assert b["manifest"]["cover"]["jpeg"]
 b["manifest"]["expenses"]=[{"title":"Test receipt","amount":"12.50","currency":"EUR","date":"2027-01-01","doc":"test.pdf"}]
 assert c.put(url,headers=h,json=b).status_code==200
 with zipfile.ZipFile(io.BytesIO(c.get(url+"/export").content)) as z:
  manifest=json.loads(z.read("manifest.json"))
  assert manifest["bookings"]==m["bookings"]
  assert manifest["cover"]["jpeg"]
  assert manifest["expenses"][0]["amount"]=="12.50"
  assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(p+"/geocode",headers=h,json={"query":"Test","key":"test"}).status_code==423
 assert c.post(p+"/analyze-booking",headers=h,json={"text":"Test"}).status_code==423
 c.close()

def test_groq_requires_literal_source(monkeypatch,tmp_path):
 monkeypatch.setattr(tools.email_intake,"load_config",lambda _:{"groq_api_key":"test","groq_model":"test"})
 monkeypatch.setattr(tools,"json_fetch",lambda *a,**k:{"choices":[{"message":{"content":json.dumps({"title":"Hotel Test","price":"99 EUR","place":"Invented city"})}}]})
 result=tools.analyze_booking(tmp_path,"Hotel Test, 99 EUR")
 assert result["title"]=="Hotel Test" and result["price"]=="99 EUR"
 assert result["place"]==""

def test_geocode_candidates(monkeypatch):
 monkeypatch.setattr(tools,"json_fetch",lambda *a,**k:{"results":[{"lat":45.1,"lon":11.1,"formatted":"Test location"},{"lat":100,"lon":0}]})
 assert len(tools.geocode("Test","test"))==1


def test_photo_search_fallback_and_licences(monkeypatch):
 calls=[]
 def candidate(id,license):
  return {"pageid":id,"title":"Test photo","imageinfo":[{"thumburl":"https://upload.wikimedia.org/test.jpg","mime":"image/jpeg","extmetadata":{"LicenseShortName":{"value":license},"Artist":{"value":"Author"}}}]}
 def fake(params):
  calls.append(params)
  if params.get("list")=="search":
   ids=[1] if params["srsearch"].startswith("filetype:") else [2,3]
   return {"query":{"search":[{"pageid":i} for i in ids]}}
  if params["pageids"]=="1":return {"query":{"pages":[candidate(1,"CC BY-NC 4.0")]}}
  return {"query":{"pages":[candidate(2,"CC BY-SA 4.0"),candidate(3,"CC BY-ND 4.0")]}}
 monkeypatch.setattr(tools,"commons",fake)
 result=tools.commons_diagnostics("Los Angeles")
 assert [r["pageid"] for r in result["results"]]==[2]
 assert result["found"]==3 and result["with_license"]==3
 assert len(calls)==4 and calls[0]["srlimit"]==30

def test_wikimedia_error_is_not_empty(monkeypatch):
 import pytest
 from fastapi import HTTPException
 monkeypatch.setattr(tools,"json_fetch",lambda *a,**kw:{"error":{"code":"test"}})
 with pytest.raises(HTTPException) as e:tools.photos_search("Test")
 assert e.value.status_code==502


def test_pexels_services_private_and_photo(tmp_path,monkeypatch):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(p+"/services",headers=h,json={"pexels":"synthetic-secret","geoapify":"synthetic-geo"}).status_code==200
 cfg=c.get(p+"/services").json()
 assert cfg=={"pexels_configured":True,"geoapify_configured":True}
 assert b"synthetic-secret" not in (tmp_path/"personal"/"trips.sqlite3").read_bytes()
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 url=p+"/trips/"+m["trip"]["id"]
 img=io.BytesIO();Image.new("RGB",(300,200),"navy").save(img,"PNG")
 pic=tools.photo(img.getvalue())
 monkeypatch.setattr(tools,"pexels_search",lambda q,k:[{"pageid":42}] if k=="synthetic-secret" else [])
 monkeypatch.setattr(tools,"pexels_photo",lambda id,k:pic)
 assert c.post(p+"/photos/search",headers=h,json={"provider":"pexels","query":"Test"}).json()==[{"pageid":42}]
 r=c.post(url+"/photo",headers=h,json={"provider":"pexels","pageid":42,"target":"day:2027-01-01"})
 assert r.status_code==200,r.text
 b=c.get(url).json()
 assert b["manifest"]["travel_photos"]["day:2027-01-01"]==pic
 assert b["manifest"]["bookings"]==m["bookings"]
 assert b"synthetic-secret" not in c.get(url+"/export").content
 assert c.post(url+"/photo",headers=h,json={"provider":"pexels","pageid":42,"target":"day:2027-02-01"}).status_code==400
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.get(p+"/services").status_code==423
 c.close()

def test_pexels_rejects_untrusted_image_hosts(monkeypatch):
 def item(host):
  return {"id":123,"alt":"test","photographer":"Test","url":"https://www.pexels.com/photo/test-123/","src":{"medium":"https://"+host+"/test.jpg","landscape":"https://"+host+"/test.jpg"}}
 monkeypatch.setattr(tools,"pexels_request",lambda *a,**kw:{"photos":[item("images.pexels.com"),item("example.org")]})
 assert len(tools.pexels_search("Test","test"))==1


def test_default_photo_provider_without_api_key(tmp_path,monkeypatch):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 monkeypatch.setattr(tools,"photos_search",lambda q:[{"pageid":42,"title":"Synthetic photo"}])
 assert c.post(p+"/photos/search",headers=h,json={"query":"Test"}).json()==[{"pageid":42,"title":"Synthetic photo"}]
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 img=io.BytesIO();Image.new("RGB",(80,60),"navy").save(img,"PNG")
 pic=tools.photo(img.getvalue())
 monkeypatch.setattr(tools,"commons_photo",lambda id:pic)
 url=p+"/trips/"+m["trip"]["id"]
 assert c.post(url+"/photo",headers=h,json={"pageid":42,"target":"cover"}).status_code==200
 assert c.get(url).json()["manifest"]["cover"]==pic
 c.close()
