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
  if params["gsrsearch"].startswith("filetype:"):return {"query":{"pages":[candidate(1,"CC BY-NC 4.0")]}}
  return {"query":{"pages":[candidate(2,"CC BY-SA 4.0"),candidate(3,"CC BY-ND 4.0")]}}
 monkeypatch.setattr(tools,"commons",fake)
 result=tools.photos_search("Los Angeles")
 assert [r["pageid"] for r in result]==[2]
 assert len(calls)==2 and calls[0]["gsrlimit"]==30

def test_wikimedia_error_is_not_empty(monkeypatch):
 import pytest
 from fastapi import HTTPException
 monkeypatch.setattr(tools,"json_fetch",lambda *a,**kw:{"error":{"code":"test"}})
 with pytest.raises(HTTPException) as e:tools.photos_search("Test")
 assert e.value.status_code==502
