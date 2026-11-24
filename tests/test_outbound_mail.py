"""Cloudflare send integration tests: synthetic recipients and mocked network only."""
import base64,json,uuid
from datetime import datetime,timezone
from test_workspace import init,create_user,sign_in
from app import outbound_mail

def config(c,h):
 return c.post("/api/outbound-mail/config",headers=h,json={
  "account_id":"a"*32,"sender":"calendar@send.example.org","token":"synthetic-token-only",
  "recipients":["test@example.org","second@example.org"]})
def body(**kwargs):
 return {"request_id":uuid.uuid4().hex,"recipient":"test@example.org",**kwargs}
def test_config_gate_encryption_and_manual_ics(tmp_path,monkeypatch):
 c,h=init(tmp_path);sent=[]
 def mock(cfg,recipient,ics,subject,text):
  sent.append((recipient,ics,subject))
  return ("delivered","Test consegnato")
 monkeypatch.setattr(outbound_mail,"provider_send",mock)
 clock=[2000000000]
 # Replace only the module's time reference; don't modify auth/session time globally.
 from types import SimpleNamespace
 monkeypatch.setattr(outbound_mail,"time",SimpleNamespace(time=lambda:clock[0]))
 r=config(c,h);assert r.status_code==200,r.text
 assert r.json()["token_configured"] and not r.json()["enabled"]
 assert "synthetic-token-only" not in r.text
 assert "synthetic-token-only" not in (tmp_path/"outbound-mail-local.json").read_text()
 assert (tmp_path/"outbound-mail-local.json").stat().st_mode&0o777==0o600
 assert c.post("/api/outbound-mail/enable",headers=h,json={"enabled":True,"confirmed_received":True}).status_code==400
 task=c.post("/api/tasks",headers=h,json={"title":"Synthetic deadline","due_at":"2026-12-01","description":"Private description"}).json()["id"]
 assert c.post("/api/outbound-mail/send-ics",headers=h,json=body(task_ids=[task],confirmed=True)).status_code==409
 assert c.post("/api/outbound-mail/test",headers=h,json=body(recipient="not-allowed@example.org")).status_code==403
 test=body()
 r=c.post("/api/outbound-mail/test",headers=h,json=test);assert r.status_code==200,r.text
 assert r.json()["status"]=="delivered" and len(sent)==1
 assert "evento fittizio" in sent[0][1]
 assert "Synthetic deadline" not in sent[0][1]
 assert c.post("/api/outbound-mail/test",headers=h,json=test).json()["duplicate"]
 assert len(sent)==1
 assert c.post("/api/outbound-mail/enable",headers=h,json={"enabled":True}).status_code==400
 assert c.post("/api/outbound-mail/enable",headers=h,json={"enabled":True,"confirmed_received":True}).json()["enabled"]
 assert c.post("/api/outbound-mail/send-ics",headers=h,json=body(task_ids=[task],confirmed=False)).status_code==400
 assert c.post("/api/outbound-mail/send-ics",headers=h,json=body(task_ids=[task],confirmed=True)).status_code==429
 clock[0]+=11
 r=c.post("/api/outbound-mail/send-ics",headers=h,json=body(task_ids=[task],confirmed=True))
 assert r.status_code==200,r.text
 assert "Synthetic deadline" in sent[1][1]
 assert "Private description" not in sent[1][1]
 clock[0]+=11
 review=c.post("/api/tasks",headers=h,json={"title":"Review","due_at":"2026-12-01","status":"review"}).json()["id"]
 assert c.post("/api/outbound-mail/send-ics",headers=h,json=body(task_ids=[review],confirmed=True)).status_code==400
 assert len(sent)==2
 assert len(c.get("/api/outbound-mail/history").json())==2
 assert "test@example.org" not in c.get("/api/outbound-mail/history").text
 create_user(c,h,"colleague");sign_in(c,h,"colleague")
 assert c.get("/api/outbound-mail/config").status_code==403
 assert c.post("/api/outbound-mail/test",headers=h,json=body()).status_code==403
 c.close()

def test_provider_payload_and_unknown_status(monkeypatch):
 sent=[]
 class FakeResponse:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def read(self,n):return json.dumps({"success":True,"result":{"queued":["test@example.org"],"delivered":[]}}).encode()
 class Opener:
  def open(self,req,timeout):
   sent.append(req)
   return FakeResponse()
 monkeypatch.setattr(outbound_mail.request,"build_opener",lambda *args:Opener())
 cfg={"account_id":"a"*32,"sender":"calendar@send.example.org","token":"test-token"}
 result=outbound_mail.provider_send(cfg,"test@example.org","BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n","Test","Body")
 assert result[0]=="queued"
 req=sent[0]
 assert req.full_url=="https://api.cloudflare.com/client/v4/accounts/"+("a"*32)+"/email/sending/send"
 assert req.get_header("Authorization")=="Bearer test-token"
 data=json.loads(req.data)
 attachment=data["attachments"][0]
 assert attachment["type"]=="text/calendar" and attachment["disposition"]=="attachment"
 assert base64.b64decode(attachment["content"]).decode()=="BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
 class Timeout:
  def open(self,*args,**kwargs):raise TimeoutError("secret should not be logged")
 monkeypatch.setattr(outbound_mail.request,"build_opener",lambda *args:Timeout())
 status,detail=outbound_mail.provider_send(cfg,"test@example.org","ICS","Test","Body")
 assert status=="unknown" and "secret" not in detail

def test_web_outbound_controls(tmp_path):
 c,h=init(tmp_path);s=c.get("/assets/app.js").text
 for x in ("Posta in uscita · Cloudflare","Invia ICS via email","Invia email di prova con ICS","/outbound-mail/send-ics","Ho ricevuto e aperto"):
  assert x in s
 c.close()
