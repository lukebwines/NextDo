"""Gmail OAuth, read-only label polling and idempotent imports; synthetic tests only."""
import base64
import json
import urllib.parse
from email.message import EmailMessage
from pathlib import Path

from test_workspace import init, create_user, sign_in


def sample_email():
 msg = EmailMessage()
 msg["From"] = "Original sender <synthetic@example.org>"
 msg["To"] = "luca.belduvini+nextdo@gmail.com"
 msg["Subject"] = "Test automatico NextDo"
 msg.set_content("Entro il 10 dicembre 2026 predisporre la relazione.\n")
 return base64.urlsafe_b64encode(msg.as_bytes()).decode().rstrip("=")


def settings(client, csrf):
 r = client.post("/api/gmail-auto/config", headers=csrf, json={
   "client_id": "1234567890-abc.apps.googleusercontent.com",
   "client_secret": "fake-test-secret",
   "redirect_uri": "https://nextdo.example.org/api/gmail-auto/callback",
   "enabled": False})
 assert r.status_code == 200, r.text
 return r.json()


def connect(client, csrf, monkeypatch):
 from app import gmail_auto as gmail
 settings(client, csrf)
 monkeypatch.setattr(gmail, "_exchange",
  lambda cfg, fields: {"refresh_token": "refresh-test-secret",
                       "access_token": "access-test-secret",
                       "scope": gmail.GOOGLE_SCOPE})
 monkeypatch.setattr(gmail, "_gmail_get",
  lambda token, endpoint, params=None: {"emailAddress": "synthetic@gmail.com"})
 r = client.post("/api/gmail-auto/connect", headers=csrf)
 assert r.status_code == 200, r.text
 query = urllib.parse.parse_qs(urllib.parse.urlsplit(r.json()["authorization_url"]).query)
 assert query["scope"][0] == gmail.GOOGLE_SCOPE
 assert query["access_type"][0] == "offline"
 assert query["code_challenge_method"][0] == "S256"
 state = query["state"][0]
 callback = client.get("/api/gmail-auto/callback?code=synthetic&state=" + state, follow_redirects=False)
 assert callback.status_code == 303, callback.text
 assert callback.headers["location"] == "/?gmail=connected"
 assert client.get("/api/gmail-auto/config").json()["connected"] is True
 return gmail


def test_config_and_oauth_redacts_refresh_and_client_secret(tmp_path, monkeypatch):
 client, csrf = init(tmp_path)
 gmail = connect(client, csrf, monkeypatch)
 stored = (tmp_path / "gmail-auto-local.json").read_text()
 assert "fake-test-secret" not in stored
 assert "refresh-test-secret" not in stored
 assert "enc:" in stored
 public = client.get("/api/gmail-auto/config").json()
 assert public["account"] == "synthetic@gmail.com"
 assert public["client_secret_configured"] and public["connected"] and not public["enabled"]
 assert "refresh_token" not in public and "client_secret" not in public
 r = client.get("/api/gmail-auto/callback?code=synthetic&state=invalid", follow_redirects=False)
 assert r.status_code == 400
 client.close()


def test_admin_only_and_enable_requires_google_connection(tmp_path):
 client, csrf = init(tmp_path)
 r = client.post("/api/gmail-auto/config", headers=csrf, json={"enabled": True})
 assert r.status_code == 400
 create_user(client, csrf, "colleague")
 sign_in(client, csrf, "colleague")
 assert client.get("/api/gmail-auto/config").status_code == 403
 assert client.get("/api/gmail-auto/history").status_code == 403
 assert client.post("/api/gmail-auto/run", headers=csrf).status_code == 403
 client.close()


def test_labeled_message_creates_only_unverified_private_tasks_once(tmp_path, monkeypatch):
 client, csrf = init(tmp_path)
 gmail = connect(client, csrf, monkeypatch)
 cfg = gmail._read(tmp_path)
 enabled = client.post("/api/gmail-auto/config", headers=csrf, json={
   "client_id": cfg["client_id"], "client_secret": "",
   "redirect_uri": cfg["redirect_uri"], "enabled": True})
 assert enabled.status_code == 200, enabled.text
 assert enabled.json()["enabled"] is True
 now = gmail.millis()
 ids = ["first"]
 monkeypatch.setattr(gmail, "_access_token", lambda cfg: "access-test-secret")
 def fake_gmail(token, endpoint, params=None):
  if endpoint == "labels":
   return {"labels": [{"id": "Label_123", "name": "NextDo"},
                       {"id": "INBOX", "name": "INBOX"}]}
  if endpoint == "messages":
   assert params["labelIds"] == "Label_123"
   return {"messages": [{"id": i} for i in ids]}
  if endpoint.startswith("messages/"):
   return {"id": endpoint.split("/")[-1], "threadId": "thread-1",
           "labelIds": ["Label_123"], "internalDate": str(now + 1000),
           "raw": sample_email()}
  raise AssertionError("Unexpected API endpoint: "+endpoint)
 monkeypatch.setattr(gmail, "_gmail_get", fake_gmail)
 from app import email_intake
 calls = []
 def fake_analyze(cfg, src):
  calls.append(src)
  return {"proposals": [
   {"title": "Predisporre la relazione", "evidence": "Entro il 10 dicembre 2026 predisporre la relazione.",
    "due_date": "2026-12-10", "description": "Azione proposta: predisporre il documento"}
  ]}
 monkeypatch.setattr(email_intake, "analyze", fake_analyze)
 first = client.post("/api/gmail-auto/run", headers=csrf)
 assert first.status_code == 200, first.text
 assert first.json()["created"] == 1
 tasks = client.get("/api/tasks").json()
 assert len(tasks) == 1
 task = tasks[0]
 assert task["status"] == "review"
 assert task["scope"] == "personal"
 assert task["assigned_to"] is None
 assert task["due_at"] == "2026-12-10"
 assert "ID messaggio Gmail: first" in task["description"]
 assert "Frase originale:" in task["description"]
 assert client.post("/api/tasks/"+str(task["id"])+"/toggle", headers=csrf).status_code == 400
 assert client.patch("/api/tasks/"+str(task["id"])+"/status", headers=csrf,
                     json={"status": "done"}).status_code == 400
 second = client.post("/api/gmail-auto/run", headers=csrf)
 assert second.status_code == 200
 assert second.json()["created"] == 0
 # A second message with identical content may not generate duplicate tasks.
 ids.insert(0, "forwarded-again")
 third = client.post("/api/gmail-auto/run", headers=csrf)
 assert third.status_code == 200
 assert third.json()["created"] == 0
 assert any(r["status"] == "duplicate" for r in client.get("/api/gmail-auto/history").json())
 assert len(client.get("/api/tasks").json()) == 1
 assert len(calls) == 1
 client.close()


def test_only_nextdo_label_and_messages_after_enabling(tmp_path, monkeypatch):
 client, csrf = init(tmp_path)
 gmail = connect(client, csrf, monkeypatch)
 cfg = gmail._read(tmp_path)
 client.post("/api/gmail-auto/config", headers=csrf, json={
   "client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"], "enabled": True})
 monkeypatch.setattr(gmail, "_access_token", lambda c: "access-test-secret")
 def fake_get(token, endpoint, params=None):
  if endpoint == "labels":
   return {"labels": [{"id": "only-nextdo", "name": "NextDo"}]}
  if endpoint == "messages":
   return {"messages": [{"id": "old"}, {"id": "different-label"}]}
  return {"id": endpoint.split("/")[-1], "labelIds": (
          ["INBOX"] if endpoint.endswith("different-label") else ["only-nextdo"]),
          "internalDate": "1000", "raw": sample_email()}
 monkeypatch.setattr(gmail, "_gmail_get", fake_get)
 from app import email_intake
 monkeypatch.setattr(email_intake, "analyze",
   lambda cfg, src: (_ for _ in ()).throw(AssertionError("Should not process old emails")))
 result = client.post("/api/gmail-auto/run", headers=csrf)
 assert result.status_code == 200, result.text
 assert result.json()["created"] == 0
 assert not client.get("/api/tasks").json()
 assert len(client.get("/api/gmail-auto/history").json()) == 2
 client.close()
