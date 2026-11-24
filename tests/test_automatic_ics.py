"""Automatic calendar mail: only synthetic data, no network."""
import sqlite3,uuid
from email.message import EmailMessage
from test_workspace import init,create_user,sign_in
from test_cloudflare_mail import setup,deliver,RECIPIENT,SENDER
from test_outbound_mail import config
from app import automatic_ics,calendar_export,email_intake,outbound_mail

RECIP="test@example.org"
def activate(c,h,monkeypatch):
 assert config(c,h).status_code==200
 sent=[]
 def provider(cfg,recipient,ics,subject,body):
  sent.append((recipient,ics,subject,body))
  return "queued","Test queued"
 monkeypatch.setattr(outbound_mail,"provider_send",provider)
 r=c.post("/api/outbound-mail/test",headers=h,json={"recipient":RECIP,"request_id":uuid.uuid4().hex})
 assert r.status_code==200,r.text
 assert c.post("/api/outbound-mail/enable",headers=h,json={"enabled":True,"confirmed_received":True}).status_code==200
 return sent

def rule(c,h,enabled=True,recipient=RECIP):
 return c.post("/api/outbound-mail/automatic-ics",headers=h,json={"enabled":enabled,"recipient":recipient,"confirmed":True})

def message(subject="Test agenda",body="Inviare la relazione entro il 10 dicembre 2099.\nLa riunione si terrà il 12 dicembre 2099 alle ore 09:30.\nOccorre verificare la scheda il 13 dicembre 2099.\nPossiamo sentirci nei prossimi giorni?\n"):
 msg=EmailMessage()
 msg["From"]=SENDER;msg["To"]=RECIPIENT;msg["Subject"]=subject
 msg["Date"]="Mon, 23 Nov 2026 10:00:00 +0100"
 msg.set_content(body)
 return msg.as_bytes()

def fake_ai(cfg,source):
 # Feed real normalization and date validation with synthetic literal evidence.
 return {"proposals":[
  {"title":"Inviare relazione","kind":"task","date":"2099-12-10","evidence":"Inviare la relazione entro il 10 dicembre 2099."},
  {"title":"Riunione","kind":"appointment","date":"2099-12-12","evidence":"La riunione si terrà il 12 dicembre 2099 alle ore 09:30.","time_evidence":"alle ore 09:30"},
  {"title":"Verificare scheda","kind":"task","date":"2099-12-13","evidence":"Occorre verificare la scheda il 13 dicembre 2099."},
  {"title":"Concordare incontro","kind":"appointment","date":"","evidence":"Possiamo sentirci nei prossimi giorni?"}
 ]}

def test_auto_rule_multiple_dates_dedup_and_review(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h);sent=activate(c,h,monkeypatch)
 monkeypatch.setattr(email_intake,"_call_groq",fake_ai)
 from app import main
 assert deliver(c,secret,message("Before activation")).status_code==202
 assert rule(c,h,recipient="unverified@example.org").status_code==400
 assert rule(c,h).status_code==200
 assert c.post("/api/cloudflare-mail/process",headers=h).status_code==200
 # Previously received messages are never retroactively sent.
 assert c.get("/api/outbound-mail/automatic-ics").json()["history"]==[]
 # Use a different literal evidence/date for new mail; old task fingerprints are retained.
 raw=message("New agenda",body="Inviare la relazione entro il 20 dicembre 2099.\nLa riunione si terrà il 22 dicembre 2099 alle ore 09:30.\nOccorre verificare la scheda il 23 dicembre 2099.\nPossiamo sentirci nei prossimi giorni?\n")
 def new_ai(cfg,source):
  out=fake_ai(cfg,source)
  for item in out["proposals"]:
   for before,after in (("10","20"),("12 dicembre","22 dicembre"),("13 dicembre","23 dicembre")):
    item["evidence"]=item["evidence"].replace(before,after)
   item["date"]={"2099-12-10":"2099-12-20","2099-12-12":"2099-12-22","2099-12-13":"2099-12-23"}.get(item["date"],item["date"])
  return out
 monkeypatch.setattr(email_intake,"_call_groq",new_ai)
 assert deliver(c,secret,raw).status_code==202
 assert c.post("/api/cloudflare-mail/process",headers=h).status_code==200
 history=c.get("/api/outbound-mail/automatic-ics").json()["history"]
 assert len(history)==1 and history[0]["status"]=="queued",history
 with main.conn() as db:db.execute("UPDATE outbound_mail_log SET created_epoch=0")
 automatic_ics.run_one(main.conn,tmp_path)
 assert len(sent)==2
 recipient,ics,subject,body=sent[-1]
 unfolded=ics.replace("\r\n ","")
 assert recipient==RECIP and subject==automatic_ics.MARKER
 assert unfolded.count("BEGIN:VEVENT")==3 and unfolded.count("STATUS:TENTATIVE")==3
 assert "[DA VERIFICARE]" in unfolded
 assert "DTSTART:20991222T083000Z" in unfolded
 assert "DTSTART;VALUE=DATE:20991223" in unfolded
 assert "Frase originale" not in unfolded and "Possiamo sentirci" not in unfolded
 assert all(t["status"]=="review" for t in c.get("/api/tasks").json())
 assert deliver(c,secret,raw).json()["duplicate"]
 automatic_ics.run_one(main.conn,tmp_path)
 assert len(sent)==2
 assert c.get("/api/outbound-mail/automatic-ics").json()["history"][0]["status"]=="provider_queued"
 # Provider acceptance must not block the next local queue item.
 with main.conn() as db:db.execute("UPDATE outbound_mail_log SET created_epoch=0")
 automatic_ics.run_one(main.conn,tmp_path)
 assert len(sent)==2
 assert rule(c,h,False).status_code==200
 assert not c.get("/api/outbound-mail/automatic-ics").json()["enabled"]
 c.close()

def test_auto_eligibility_and_cancellation(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h);sent=activate(c,h,monkeypatch)
 assert rule(c,h).status_code==200
 monkeypatch.setattr(email_intake,"_call_groq",fake_ai)
 assert deliver(c,secret,message()).status_code==202
 assert c.post("/api/cloudflare-mail/process",headers=h).status_code==200
 assert len(c.get("/api/outbound-mail/automatic-ics").json()["history"])==1
 assert rule(c,h,False).status_code==200
 from app import main
 automatic_ics.run_one(main.conn,tmp_path)
 assert len(sent)==1
 assert c.get("/api/outbound-mail/automatic-ics").json()["history"][0]["status"]=="cancelled"
 create_user(c,h,"other");sign_in(c,h,"other")
 assert c.get("/api/outbound-mail/automatic-ics").status_code==403
 assert rule(c,h).status_code==403
 c.close()

def test_auto_strict_evidence():
 source={"text":"La riunione si è svolta il 12 dicembre 2099. Potremmo incontrarci il 13 dicembre 2099. La riunione si terrà il 14 dicembre 2099 alle ore 09:30.","date":"Mon, 23 Nov 2026 10:00:00 +0100"}
 def prop(e,d,clock=""):
  return {"kind":"appointment","evidence":e,"due_date":d,"appointment_time":clock}
 assert not automatic_ics.eligible(prop("La riunione si è svolta il 12 dicembre 2099.","2099-12-12"),source,automatic_ics.TZ)
 assert not automatic_ics.eligible(prop("Potremmo incontrarci il 13 dicembre 2099.","2099-12-13"),source,automatic_ics.TZ)
 assert automatic_ics.eligible(prop("La riunione si terrà il 14 dicembre 2099 alle ore 09:30.","2099-12-14","09:30"),source,automatic_ics.TZ)
 assert not automatic_ics.eligible(prop("La riunione si terrà il 14 dicembre 2099 alle ore 09:30.","2099-12-14","11:30"),source,automatic_ics.TZ)
 assert not automatic_ics.eligible(prop("Inventata","2099-12-14"),source,automatic_ics.TZ)
