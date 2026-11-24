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


def test_ai_image_preview_and_accept(tmp_path,monkeypatch):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(p+"/services",headers=h,json={"image_ai":"synthetic-secret","geoapify":"synthetic-geo"}).status_code==200
 assert c.get(p+"/services").json()=={"image_ai_configured":True,"geoapify_configured":True}
 assert b"synthetic-secret" not in (tmp_path/"personal"/"trips.sqlite3").read_bytes()
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 url=p+"/trips/"+m["trip"]["id"]
 img=io.BytesIO();Image.new("RGB",(300,200),"navy").save(img,"PNG")
 pic={**tools.photo(img.getvalue()),"credit":"Immagine illustrativa generata con AI OpenAI","license":"Generata con AI"}
 calls=[]
 def generate(prompt,key):
  calls.append((prompt,key));return pic
 monkeypatch.setattr(tools,"generate_image",generate)
 body={"target":"day:2027-01-01","prompt":"Synthetic landscape","confirm_cost":True}
 assert c.post(url+"/photo/generate",headers=h,json={**body,"confirm_cost":False}).status_code==400
 assert c.post(url+"/photo/generate",headers=h,json={**body,"target":"day:2027-02-01"}).status_code==400
 assert not calls
 r=c.post(url+"/photo/generate",headers=h,json=body)
 assert r.status_code==200,r.text
 assert calls==[("Synthetic landscape","synthetic-secret")]
 assert "travel_photos" not in c.get(url).json()["manifest"]
 token=r.json()["token"]
 assert c.post(url+"/photo/accept",headers=h,json={"token":"wrong"}).status_code==409
 assert c.post(url+"/photo/accept",headers=h,json={"token":token}).status_code==200
 b=c.get(url).json()
 assert b["manifest"]["travel_photos"]["day:2027-01-01"]==pic
 assert b["manifest"]["bookings"]==m["bookings"]
 assert c.post(url+"/photo/accept",headers=h,json={"token":token}).status_code==409
 with zipfile.ZipFile(io.BytesIO(c.get(url+"/export").content)) as z:
  assert b"synthetic-secret" not in z.read("manifest.json")
  assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
 assert c.post(p+"/photos/search",headers=h,json={"query":"Test"}).status_code==404
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(url+"/photo/generate",headers=h,json=body).status_code==423
 c.close()
