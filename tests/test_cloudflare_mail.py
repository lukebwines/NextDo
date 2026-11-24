"""Cloudflare inbound email webhook tests: synthetic only, no remote HTTP calls."""
import hashlib
import hmac
import json
import stat
import time
from email.message import EmailMessage
from test_workspace import init,create_user,sign_in

RECIPIENT="scadenze@posta.example.org"
SENDER="forwarder@example.org"

def sample(changed=False):
 msg=EmailMessage()
 msg["From"]="Forwarder <forwarder@example.org>"
 msg["To"]=RECIPIENT
 msg["Subject"]="NextDo synthetic deadline"
 msg["Date"]="Mon, 23 Nov 2026 10:00:00 +0100"
 if changed:msg["X-Routing-Test"]="second delivery"
 msg.set_content("Inviare la relazione entro il 10 dicembre 2026.\n")
 msg.add_attachment(b"private attached content",maintype="application",
                    subtype="octet-stream",filename="private.bin")
 return msg.as_bytes()

def setup(client,csrf):
 r=client.post("/api/cloudflare-mail/config",headers=csrf,json={
  "recipient":RECIPIENT,"allowed_sender":SENDER,"enabled":False})
 assert r.status_code==200,r.text
 r=client.post("/api/cloudflare-mail/secret",headers=csrf)
 assert r.status_code==200,r.text
 secret=r.json()["secret"]
 r=client.post("/api/cloudflare-mail/config",headers=csrf,json={
  "recipient":RECIPIENT,"allowed_sender":SENDER,"enabled":True})
 assert r.status_code==200,r.text
 return secret

def header(secret,raw,sender=SENDER,recipient=RECIPIENT,t=None):
 t=str(t if t is not None else int(time.time()))
 signed=(t+"\n"+sender+"\n"+recipient+"\n").encode()+raw
 sig=hmac.new(secret.encode(),signed,hashlib.sha256).hexdigest()
 return {"Content-Type":"message/rfc822","X-NextDo-Timestamp":t,
         "X-NextDo-Signature":sig,"X-NextDo-Envelope-From":sender,
         "X-NextDo-Envelope-To":recipient}

def deliver(client,secret,raw,**kwargs):
 return client.post("/api/cloudflare-mail/inbound",
    headers=header(secret,raw,**kwargs),content=raw)

def test_multiple_authorized_senders(tmp_path):
 c,h=init(tmp_path)
 secret=setup(c,h)
 second="another@example.org"
 config={"recipient":RECIPIENT,"allowed_sender":f"{SENDER}, {second.upper()}, {SENDER}","enabled":True}
 r=c.post("/api/cloudflare-mail/config",headers=h,json=config)
 assert r.status_code==200,r.text
 assert r.json()["allowed_sender"]==f"{SENDER}, {second}"
 assert deliver(c,secret,sample(),sender=SENDER).status_code==202
 assert deliver(c,secret,sample(changed=True),sender=second).status_code==202
 assert deliver(c,secret,sample(),sender="not"+second).status_code==403
 config["allowed_sender"]=f"{SENDER}, *@example.org"
 assert c.post("/api/cloudflare-mail/config",headers=h,json=config).status_code==400
 c.close()

def test_settings_only_admin_and_encrypted_secret(tmp_path):
 c,h=init(tmp_path)
 secret=setup(c,h)
 assert c.get("/api/cloudflare-mail/config").json()["secret_configured"] is True
 cfg=tmp_path/"cloudflare-mail-local.json"
 assert cfg.exists()
 assert stat.S_IMODE(cfg.stat().st_mode)==0o600
 assert secret not in cfg.read_text()
 assert "enc:" in cfg.read_text()
 assert c.get("/api/cloudflare-mail/config").json().get("secret") is None
 create_user(c,h,"colleague")
 sign_in(c,h,"colleague")
 assert c.get("/api/cloudflare-mail/config").status_code==403
 assert c.post("/api/cloudflare-mail/secret",headers=h).status_code==403
 assert c.get("/api/cloudflare-mail/history").status_code==403
 c.close()

def test_signed_delivery_encrypted_queue_review_and_dedup(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h)
 raw=sample()
 for invalid in (
   {"Content-Type":"message/rfc822"},
   header("wrong-secret",raw),
   header(secret,raw,t=int(time.time())-400),
   header(secret,raw,sender="someone@example.org")
 ):
  r=c.post("/api/cloudflare-mail/inbound",headers=invalid,content=raw)
  assert r.status_code in (401,403)
 assert not c.get("/api/tasks").json()
 received=deliver(c,secret,raw)
 assert received.status_code==202,received.text
 assert received.json()["state"]=="queued"
 queue=tmp_path/"nextdo.sqlite3"
 import sqlite3
 with sqlite3.connect(queue) as db:
  payload=db.execute("SELECT payload_encrypted FROM cloudflare_mail_inbox").fetchone()[0]
 assert "Inviare la relazione" not in payload
 assert "private attached content" not in payload
 from app import email_intake
 requests=[]
 def fake_ai(cfg,source):
  requests.append(source)
  assert "private attached content" not in source["text"]
  return {"proposals":[{
   "title":"Inviare la relazione",
   "due_date":"2026-12-10",
   "evidence":"Inviare la relazione entro il 10 dicembre 2026.",
   "description":"Azione proposta: inoltrare il documento."
  }]}
 monkeypatch.setattr(email_intake,"analyze",fake_ai)
 result=c.post("/api/cloudflare-mail/process",headers=h)
 assert result.status_code==200,result.text
 assert result.json()["created"]==1
 task=c.get("/api/tasks").json()[0]
 assert task["status"]=="review"
 assert task["scope"]=="personal"
 assert task["assigned_to"] is None
 assert task["due_at"]=="2026-12-10"
 assert "Frase originale:" in task["description"]
 assert "Origine: Cloudflare Email Routing" in task["description"]
 assert "[DA VERIFICARE]" in task["description"]
 assert c.post("/api/tasks/"+str(task["id"])+"/toggle",headers=h).status_code==400
 assert c.patch("/api/tasks/"+str(task["id"])+"/status",headers=h,
                json={"status":"done"}).status_code==400
 assert c.patch("/api/tasks/"+str(task["id"])+"/status",headers=h,
                json={"status":"todo"}).status_code==400
 assert c.post("/api/tasks/"+str(task["id"])+"/progress",headers=h,
               json={"status":"doing","note":"Try to bypass review"}).status_code==400
 payload={
  "title":task["title"],"description":task["description"],
  "kind":"task","status":"todo","priority":task["priority"],"scope":"personal",
  "labels":task["labels"],"due_at":task["due_at"],
  "assigned_to":None,"group_id":None,"completion_mode":"global",
  "display_enabled":False,"recurrence":"none","course_ids":[],"reminders":[]
 }
 confirmation=c.put("/api/tasks/"+str(task["id"]),headers=h,json=payload)
 assert confirmation.status_code==200,confirmation.text
 confirmed=c.get("/api/tasks/"+str(task["id"])).json()
 assert confirmed["status"]=="todo"
 assert "Da verificare" not in confirmed["labels"]
 assert "Scadenza confermata manualmente" in confirmed["description"]
 duplicate=deliver(c,secret,raw)
 assert duplicate.status_code==202 and duplicate.json()["duplicate"] is True
 # Forwarding headers can differ without changing the actual email text.
 duplicate_content=deliver(c,secret,sample(changed=True))
 assert duplicate_content.status_code==202
 assert duplicate_content.json()["duplicate"] is True
 assert c.post("/api/cloudflare-mail/process",headers=h).json()["created"]==0
 assert len(c.get("/api/tasks").json())==1
 assert len(requests)==1
 with sqlite3.connect(queue) as db:
  assert db.execute("SELECT payload_encrypted FROM cloudflare_mail_inbox WHERE status='processed'").fetchone()[0] is not None
 c.close()

def test_disabled_receiver_and_sender_filter(tmp_path):
 c,h=init(tmp_path)
 secret=setup(c,h)
 raw=sample()
 assert deliver(c,secret,raw,sender="not-authorized@example.org").status_code==403
 c.post("/api/cloudflare-mail/config",headers=h,json={
  "recipient":RECIPIENT,"allowed_sender":SENDER,"enabled":False})
 assert deliver(c,secret,raw).status_code==503
 assert c.get("/api/cloudflare-mail/history").json()==[]
 c.close()

def test_retries_do_not_create_tasks_on_ai_errors(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h)
 assert deliver(c,secret,sample()).status_code==202
 from app import email_intake
 from fastapi import HTTPException
 def fail_model(cfg,src):
  raise HTTPException(status_code=502,detail="GroqCloud unreachable")
 monkeypatch.setattr(email_intake,"analyze",fail_model)
 r=c.post("/api/cloudflare-mail/process",headers=h)
 assert r.status_code==200 and r.json()["errors"]==1
 assert c.get("/api/tasks").json()==[]
 history=c.get("/api/cloudflare-mail/history").json()
 assert history[0]["status"]=="retry"
 assert "GroqCloud" in history[0]["error"]
 c.close()


def test_admin_can_retry_failed_import_and_retains_queue(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h)
 assert deliver(c,secret,sample()).status_code==202
 import sqlite3
 with sqlite3.connect(tmp_path/"nextdo.sqlite3") as db:
  db.execute("UPDATE cloudflare_mail_inbox SET status='failed',attempt_count=3")
 result=c.post("/api/cloudflare-mail/retry-failed",headers=h)
 assert result.status_code==200 and result.json()["queued"]==1
 with sqlite3.connect(tmp_path/"nextdo.sqlite3") as db:
  state=db.execute("SELECT status,attempt_count FROM cloudflare_mail_inbox").fetchone()
 assert state==("retry",0)
 c.close()


def test_empty_analysis_retained_preview_and_delete(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h)
 from app import email_intake
 monkeypatch.setattr(email_intake,"analyze",lambda cfg,src:{"proposals":[],"automatically_saved":False})
 raw=sample();sha=hashlib.sha256(raw).hexdigest()
 assert deliver(c,secret,raw).status_code==202
 assert c.post("/api/cloudflare-mail/process",headers=h).json()["created"]==1
 t=c.get("/api/tasks").json()[0]
 assert t["title"].startswith("Email da esaminare")
 assert t["status"]=="review" and t["due_at"] is None
 row=c.get("/api/cloudflare-mail/history").json()[0]
 assert row["subject"]=="NextDo synthetic deadline" and row["text_available"]
 assert row["linked_tasks"][0]["task_id"]==t["id"]
 url="/api/cloudflare-mail/history/"+sha
 source=c.get(url).json()["source"]
 assert "Inviare la relazione" in source["text"] and "private attached content" not in source["text"]
 assert c.post(url+"/reanalyze",headers=h).json()["proposals"][0]["manual_review"]
 assert len(c.get("/api/tasks").json())==1
 assert c.post(url+"/requeue",headers=h).status_code==409
 assert c.delete(url+"/text",headers=h).status_code==200
 assert c.get(url).status_code==410
 assert len(c.get("/api/tasks").json())==1
 assert deliver(c,secret,raw).json()["duplicate"]
 c.close()

def test_expiration_and_legacy_empty_reforward(tmp_path,monkeypatch):
 import sqlite3
 c,h=init(tmp_path);secret=setup(c,h)
 from app import email_intake
 raw=sample();sha=hashlib.sha256(raw).hexdigest()
 assert deliver(c,secret,raw).status_code==202
 with sqlite3.connect(tmp_path/"nextdo.sqlite3") as db:
  db.execute("UPDATE cloudflare_mail_inbox SET status='processed',payload_encrypted=NULL,tasks_created=0")
 assert deliver(c,secret,raw).json()["state"]=="queued"
 monkeypatch.setattr(email_intake,"analyze",lambda cfg,src:{"proposals":[]})
 assert c.post("/api/cloudflare-mail/process",headers=h).json()["created"]==1
 with sqlite3.connect(tmp_path/"nextdo.sqlite3") as db:
  db.execute("UPDATE cloudflare_mail_inbox SET received_at=datetime('now','-31 days')")
 row=c.get("/api/cloudflare-mail/history").json()[0]
 assert not row["text_available"] and row["subject"] is None
 assert c.get("/api/cloudflare-mail/history/"+sha).status_code==410
 assert len(c.get("/api/tasks").json())==1
 c.close()

def test_retained_text_admin_only(tmp_path,monkeypatch):
 c,h=init(tmp_path);secret=setup(c,h)
 from app import email_intake
 monkeypatch.setattr(email_intake,"analyze",lambda cfg,src:{"proposals":[]})
 raw=sample();sha=hashlib.sha256(raw).hexdigest()
 assert deliver(c,secret,raw).status_code==202
 assert c.post("/api/cloudflare-mail/process",headers=h).json()["created"]==1
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 url="/api/cloudflare-mail/history/"+sha
 assert c.get(url).status_code==403
 assert c.post(url+"/reanalyze",headers=h).status_code==403
 assert c.delete(url+"/text",headers=h).status_code==403
 c.close()
