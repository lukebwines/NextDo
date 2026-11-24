"""Synthetic iCalendar export tests, no external calendar or real events."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from test_workspace import init,create_user,sign_in
from app import calendar_export

def create(c,h,**kwargs):
 r=c.post("/api/tasks",headers=h,json={"title":"Test attività",**kwargs})
 assert r.status_code==200,r.text
 return r.json()["id"]

def export(c,h,ids,details=False):
 return c.post("/api/calendar/export",headers=h,json={"task_ids":ids,"include_details":details})

def unfold(text):
 return text.replace("\r\n ","")

def test_single_and_multiple_calendar_export(tmp_path):
 c,h=init(tmp_path)
 due=create(c,h,title="Inviare relazione",due_at="2026-12-01")
 appointment=create(c,h,title="Riunione",kind="appointment",due_at="2026-12-02T10:00:00+01:00",
   description="Luogo: Aula sintetica\nCollegamento: https://example.org/meeting\nDescrizione riservata")
 unknown=create(c,h,title="Incontro",kind="appointment",due_at="2026-12-03")
 a=export(c,h,[due,appointment,unknown,due])
 assert a.status_code==200,a.text
 assert a.headers["content-type"].startswith("text/calendar")
 assert a.headers["cache-control"]=="no-store"
 assert '.ics"' in a.headers["content-disposition"]
 body=unfold(a.text)
 assert body.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
 assert body.count("BEGIN:VEVENT")==3
 assert "DTSTART;VALUE=DATE:20261201" in body and "DTEND;VALUE=DATE:20261202" in body
 assert "DTSTART:20261202T090000Z" in body
 timed=next(x for x in body.split("BEGIN:VEVENT") if "SUMMARY:Riunione" in x)
 assert "DTEND" not in timed and "DURATION" not in timed
 assert "Incontro (orario da definire)" in body
 assert "Descrizione riservata" not in body and "example.org" not in body
 d=export(c,h,[appointment],True)
 assert d.status_code==200,d.text
 assert "LOCATION:Aula sintetica" in d.text and "URL:https://example.org/meeting" in d.text
 assert "Descrizione riservata" in unfold(d.text)
 assert len(c.get("/api/tasks").json())==3
 c.close()

def test_review_missing_dates_notes_and_permissions(tmp_path):
 c,h=init(tmp_path)
 private=create(c,h,due_at="2026-12-01")
 common=create(c,h,due_at="2026-12-02",scope="common")
 review=create(c,h,due_at="2026-12-03",status="review")
 note=create(c,h,due_at="2026-12-03",kind="note")
 no_due=create(c,h)
 for tid in (review,note,no_due):
  assert export(c,h,[common,tid]).status_code==400
 assert export(c,h,[]).status_code==422
 assert c.post("/api/calendar/export",json={"task_ids":[common]}).status_code in (401,403)
 create_user(c,h,"colleague")
 sign_in(c,h,"colleague")
 assert export(c,h,[private]).status_code==403
 assert export(c,h,[common,private]).status_code==403
 assert export(c,h,[common]).status_code==200
 c.close()

def test_ics_escaping_folding_timezone_and_uid():
 tz=ZoneInfo("Europe/Rome")
 task={"id":1,"owner_id":2,"created_at":"2026-01-01 10:00:00","title":"È"*90+", a;b\\c\nATTENDEE:evil",
  "description":"Test\nBEGIN:VEVENT\nLuogo: Sala A, B\nCollegamento: javascript:alert(1)",
  "kind":"appointment","status":"todo","due_at":"2026-07-01T09:30:00"}
 now=datetime(2026,11,24,tzinfo=timezone.utc)
 a=calendar_export.calendar([task],tz,True,now)
 assert all(len(x.encode("utf-8"))<=75 for x in a.split("\r\n"))
 body=unfold(a)
 assert "DTSTART:20260701T073000Z" in body
 assert r"\, a\;b\\c\nATTENDEE:evil" in body
 assert "\r\nATTENDEE:" not in body
 assert body.count("\r\nBEGIN:VEVENT\r\n")==1
 assert "URL:" not in body
 assert r"LOCATION:Sala A\, B" in body
 uid=next(x for x in body.split("\r\n") if x.startswith("UID:"))
 task["title"]="Modificato";task["due_at"]="2026-07-02T09:30:00"
 assert uid in unfold(calendar_export.calendar([task],tz,False,now))
 task["due_at"]="2026-10-25T02:30:00"
 assert not calendar_export.eligible(task,tz)
 task["due_at"]="2026-03-29T02:30:00"
 assert not calendar_export.eligible(task,tz)

def test_ics_web_buttons(tmp_path):
 c,h=init(tmp_path)
 s=c.get("/assets/app.js").text
 for value in ("Aggiungi al calendario · ICS","Esporta ICS","calendarExportForm","Seleziona tutte","Includi descrizione","/calendar/export"):
  assert value in s
 c.close()
