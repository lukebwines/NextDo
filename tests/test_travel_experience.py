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


def test_manual_photo_for_day_and_booking(tmp_path):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 assert c.post(p+"/services",headers=h,json={"geoapify":"synthetic-geo"}).status_code==200
 assert c.get(p+"/services").json()=={"geoapify_configured":True}
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 url=p+"/trips/"+m["trip"]["id"]
 img=io.BytesIO();Image.new("RGB",(300,200),"navy").save(img,"PNG")
 for target in ["cover","day:2027-01-01","booking:"+m["bookings"][0]["id"]]:
  r=c.post(url+"/photo/upload",params={"target":target},headers=h,files={"file":("photo.png",img.getvalue(),"image/png")})
  assert r.status_code==200,r.text
 b=c.get(url).json()
 assert b["manifest"]["cover"]["jpeg"]
 assert len(b["manifest"]["travel_photos"])==2
 assert b["manifest"]["bookings"]==m["bookings"]
 with zipfile.ZipFile(io.BytesIO(c.get(url+"/export").content)) as z:
  assert z.read("documenti/test.pdf")==b"%PDF-synthetic"
 assert c.post(p+"/photos/search",headers=h,json={"query":"Test"}).status_code==404
 assert c.post(url+"/photo/generate",headers=h,json={}).status_code==404
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(url+"/photo/upload",headers=h,files={"file":("photo.png",img.getvalue(),"image/png")}).status_code==423
 c.close()


def test_multi_locations_and_daily_route(tmp_path,monkeypatch):
 c,h=init(tmp_path);p="/api/personal"
 assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
 raw,m=sample()
 assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
 url=p+"/trips/"+m["trip"]["id"]
 b=c.get(url).json()
 first={"id":"loc-first","role":"Partenza","label":"Airport A","lat":45.5,"lon":11.0}
 second={"id":"loc-second","role":"Arrivo","label":"Airport B","lat":45.8,"lon":11.2}
 b["manifest"]["bookings"][0]["locations"]=[first,second]
 b["manifest"]["bookings"][0]["fields"]=[["Terminal","T1"]]
 b["manifest"]["days"][0]["route_points"]=[first,second]
 b["manifest"]["days"][0]["route_mode"]="drive"
 assert c.put(url,headers=h,json=b).status_code==200
 assert c.post(p+"/services",headers=h,json={"geoapify":"synthetic-key"}).status_code==200
 monkeypatch.setattr(tools,"route",lambda pts,mode,key:{"distance_m":1000,"duration_s":120,"legs":[{"distance_m":1000,"duration_s":120}]} if pts==[first,second] and key=="synthetic-key" and mode=="drive" else {})
 result=c.post(url+"/route",headers=h,json={"date":b["manifest"]["days"][0]["date"]})
 assert result.status_code==200,result.text
 assert result.json()["distance_m"]==1000
 saved=c.get(url).json()
 assert saved["manifest"]["bookings"][0]["title"]==m["bookings"][0]["title"]
 assert saved["manifest"]["bookings"][0]["locations"]==[first,second]
 saved["manifest"]["bookings"][0]["locations"][0]["lat"]=100
 assert c.put(url,headers=h,json=saved).status_code==400
 assert c.post(p+"/lock",headers=h).status_code==200
 assert c.post(url+"/route",headers=h,json={"date":b["manifest"]["days"][0]["date"]}).status_code==423
 c.close()

def test_geoapify_route_order(monkeypatch):
 calls=[]
 def fake(url,**kwargs):
  calls.append(url)
  return {"features":[{"properties":{"distance":1200,"time":300,"legs":[{"distance":1200,"time":300}]}}]}
 monkeypatch.setattr(tools,"json_fetch",fake)
 pts=[{"lat":45.5,"lon":11.0},{"lat":45.6,"lon":11.2}]
 result=tools.route(pts,"walk","test-key")
 assert result["distance_m"]==1200 and result["duration_s"]==300
 from urllib.parse import urlsplit,parse_qs
 params=parse_qs(urlsplit(calls[0]).query)
 assert params["waypoints"]==["45.5,11.0|45.6,11.2"]
 assert params["mode"]==["walk"]
