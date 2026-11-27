from datetime import datetime,timezone
from app.flight_status import identity,evaluate,normalize,Lookup

CASE=("XY123","2027-01-03","AAA","BBB")
def flight(day="2027-01-03",**kwargs):
 return {"number":"XY123","from":{"iata":"AAA"},"to":{"iata":"BBB"},"status":"Scheduled",
 "departure":{"scheduled":day+"T23:00-08:00","estimated":day+"T23:15-08:00"},
 "arrival":{"scheduled":"2027-01-04T10:00+01:00"},**kwargs}

def response(*rows):
 return {"structuredContent":{"flights":list(rows)}}

def test_identity_and_ambiguity():
 b={"kind":"flight","date":"03/01/2027","fields":[["Numero volo","XY 123"]],"locations":[{"role":"Partenza","code":"AAA"},{"role":"Arrivo","code":"BBB"}]}
 assert identity(b)==CASE
 b["fields"].append(["Numero volo","XY124"])
 assert identity(b) is None

def test_local_departure_date_and_fallback():
 calls=[]
 def call(name,args):
  calls.append(name)
  return response(flight("2027-01-02") if name=="flight_status" else flight())
 r=evaluate(CASE,call,datetime(2027,1,3,tzinfo=timezone.utc))
 assert calls==["flight_status","airport_board"]
 assert r["source"]=="airport_board" and r["departure"]["delta_minutes"]==15
 assert r["arrival"]["delta_minutes"] is None

def test_wrong_day_and_duplicates():
 assert evaluate(CASE,lambda *_:response(flight("2027-01-02")))["source"] is None
 assert evaluate(CASE,lambda *_:response(flight(),flight()))["source"] is None

def test_no_estimate_is_not_punctual():
 f=flight();f["departure"].pop("estimated")
 assert normalize(f,datetime(2027,1,3,tzinfo=timezone.utc))["state"]=="Partenza programmata"

def test_conflicting_actual_and_cancellation():
 f=flight();f["status"]="Cancelled";f["departure"]["actual"]="2027-01-03T23:15-08:00"
 assert normalize(f,datetime(2027,1,5,tzinfo=timezone.utc)) is None

def test_cache_no_repeat(monkeypatch):
 from app import flight_status
 class Client:
  def call(self,*args):return response(flight())
 monkeypatch.setattr(flight_status,"Client",Client)
 lookup=Lookup()
 assert not lookup.check("synthetic-owner",CASE)["cached"]
 assert lookup.check("synthetic-owner",CASE)["cached"]
 assert lookup.check("synthetic-owner",CASE,True)["cached"]
