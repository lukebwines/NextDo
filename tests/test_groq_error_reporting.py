"""Synthetic Groq transport tests: never use a real API key or send email text."""
from io import BytesIO
import json
import urllib.error
import urllib.request
import pytest
from fastapi import HTTPException


def source():
 return {"subject": "Test NextDo", "sender": "", "date": "",
         "text": "Inviare il documento entro il 15 dicembre 2026.",
         "source_hash": "synthetic"}


def config():
 return {"groq_model": "openai/gpt-oss-120b", "groq_api_key": "gsk_fake_local_test"}


def test_groq_user_agent_and_json_response(monkeypatch):
 from app import email_intake
 captured = {}

 class Response:
  def __enter__(self):
   return self
  def __exit__(self, *args):
   return None
  def read(self, limit):
   return json.dumps({"choices": [{"message": {"content": '{"proposals":[]}'}}]}).encode()

 class Opener:
  def open(self, request, timeout):
   captured["ua"] = request.get_header("User-agent")
   captured["url"] = request.full_url
   captured["timeout"] = timeout
   captured["payload"] = json.loads(request.data)
   return Response()

 monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
 result = email_intake._call_groq(config(), source())
 assert result == {"proposals": []}
 assert captured["ua"].startswith("NextDo/")
 assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
 assert captured["payload"]["model"] == "openai/gpt-oss-120b"
 assert captured["timeout"] == 40


@pytest.mark.parametrize("status, fragment", [
 (400, "modello e parametri"),
 (401, "chiave API"),
 (403, "Cloudflare"),
 (404, "modello non disponibile"),
 (429, "limite di utilizzo"),
 (500, "temporaneamente"),
])
def test_groq_errors_are_actionable_and_never_leak_secrets(monkeypatch, status, fragment):
 from app import email_intake
 class Opener:
  def open(self, request, timeout):
   raise urllib.error.HTTPError(request.full_url, status, "test response",
                                {"Retry-After": "3"} if status == 429 else {},
                                BytesIO(b'{"error":"secret from provider"}'))
 monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Opener())
 with pytest.raises(HTTPException) as exc:
  email_intake._call_groq(config(), source())
 assert exc.value.status_code == 502
 assert fragment in exc.value.detail
 assert "gsk_fake_local_test" not in exc.value.detail
 assert "secret from provider" not in exc.value.detail


def test_missing_key_is_reported_before_network(monkeypatch):
 from app import email_intake
 with pytest.raises(HTTPException) as exc:
  email_intake._call_groq({"groq_model": "openai/gpt-oss-120b"}, source())
 assert exc.value.status_code == 400
 assert "chiave API" in exc.value.detail
