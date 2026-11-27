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


def test_multiple_segments_are_explicit_and_distinct():
 from app.flight_status import segment_cases,select_case
 from fastapi import HTTPException
 import pytest
 rows=[{"number":"xy 123","date":"03/01/2027","from":"aaa","to":"bbb"},{"number":"XY124","date":"2027-01-04","from":"BBB","to":"CCC"}]
 normalized=segment_cases(rows)
 assert select_case({"flight_segments":normalized},0)==CASE
 assert select_case({"flight_segments":normalized},1)==("XY124","2027-01-04","BBB","CCC")
 with pytest.raises(HTTPException):segment_cases([rows[0],rows[0]])
 with pytest.raises(HTTPException):select_case({"flight_segments":normalized},None)
 with pytest.raises(HTTPException):select_case({"flight_segments":[]},0)
 with pytest.raises(HTTPException):segment_cases([dict(rows[0],date="tomorrow")])


def test_auto_import_summary_preserves_unknown_connections():
 from app.flight_import import suggest
 trip={"start":"2027-01-03","end":"2027-01-12"}
 b={"lines":[["Andata","Dom 3 gennaio · Test AAA 11:45 → Test CCC 18:30; 1 scalo; XY123 + XY124"],["Ritorno","11 gennaio · Test CCC 18:25 → Test AAA 19:40; XY125 + XY126"],["Bagaglio","XY987"]]}
 result=suggest(b,trip,{})["segments"]
 assert result==[
  {"number":"XY123","date":"2027-01-03","from":"AAA","to":""},
  {"number":"XY124","date":"","from":"","to":"CCC"},
  {"number":"XY125","date":"2027-01-11","from":"CCC","to":""},
  {"number":"XY126","date":"","from":"","to":"AAA"}]

def test_auto_import_local_pdf_adds_only_explicit_data(monkeypatch):
 from app import flight_import
 monkeypatch.setattr(flight_import,"pdf_text",lambda raw:"XY123 03 Jan 2027 AAA → BBB\nXY124 03 Jan 2027 BBB → CCC")
 b={"lines":[["Andata","3 gennaio · Test AAA 11:45 → Test CCC 18:30; XY123 + XY124"]],"doc":"synthetic.pdf"}
 trip={"start":"2027-01-03","end":"2027-01-12"}
 result=flight_import.suggest(b,trip,{"synthetic.pdf":b"synthetic"})
 assert result["pdf_read"]==1
 assert result["segments"]==[
 {"number":"XY123","date":"2027-01-03","from":"AAA","to":"BBB"},
 {"number":"XY124","date":"2027-01-03","from":"BBB","to":"CCC"}]

def test_auto_import_conflict_does_not_guess(monkeypatch):
 from app import flight_import
 monkeypatch.setattr(flight_import,"pdf_text",lambda raw:"XY123 03 Jan 2027 AAA → CCC")
 b={"lines":[["Volo","XY123 03 Jan 2027 AAA → BBB"]],"doc":"synthetic.pdf"}
 rows=flight_import.suggest(b,{"start":"2027-01-03","end":"2027-01-12"},{"synthetic.pdf":b"x"})["segments"]
 assert rows[0]["to"]==""
