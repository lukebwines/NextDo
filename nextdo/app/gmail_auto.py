"""Gmail OAuth read-only ingestion: label NextDo -> Groq -> unverified private tasks.

No automatic Google mailbox mutations. Raw email bodies and OAuth access tokens are
never stored. The refresh token and client secret are encrypted on disk.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from . import email_intake

LOG = logging.getLogger(__name__)
GOOGLE_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALLBACK_PATH = "/api/gmail-auto/callback"
LABEL = "NextDo"
POLL_SECONDS = 300
BATCH_LIMIT = 20
MAX_PAGES = 5
RUN_LOCK = threading.Lock()
TOKEN_LOCK = threading.Lock()
ACCESS_CACHE = {"value": "", "expires": 0, "refresh_id": ""}
WORKER_STARTED = False


def fail(message, status=400):
 raise HTTPException(status_code=status, detail=message)


def utc():
 return datetime.now(timezone.utc).isoformat()


def millis():
 return int(time.time() * 1000)


def config_path(data_path):
 return Path(data_path) / "gmail-auto-local.json"


def _read(data_path):
 path = config_path(data_path)
 if not path.exists():
  return {}
 try:
  raw = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(raw, dict):
   raise ValueError("Invalid Gmail settings")
  for name in ("client_secret", "refresh_token"):
   value = raw.get(name, "")
   if value:
    if not isinstance(value, str) or not value.startswith("enc:"):
     fail("Credenziali Gmail non cifrate nella configurazione", 500)
    raw[name] = email_intake._cipher(data_path).decrypt(value[4:].encode("ascii")).decode("utf-8")
  return raw
 except HTTPException:
  raise
 except Exception:
  fail("Impossibile leggere le impostazioni Gmail protette", 500)


def _write(data_path, values):
 target = config_path(data_path)
 safe = dict(values)
 cipher = email_intake._cipher(data_path)
 for name in ("client_secret", "refresh_token"):
  if safe.get(name):
   safe[name] = "enc:" + cipher.encrypt(safe[name].encode("utf-8")).decode("ascii")
 tmp = target.with_name(target.name + "." + secrets.token_hex(5) + ".tmp")
 try:
  fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
  with os.fdopen(fd, "w", encoding="utf-8") as out:
   json.dump(safe, out, ensure_ascii=False)
  os.replace(tmp, target)
 finally:
  tmp.unlink(missing_ok=True)


def _public(cfg):
 return {"client_id": cfg.get("client_id", ""),
         "client_secret_configured": bool(cfg.get("client_secret")),
         "redirect_uri": cfg.get("redirect_uri", ""),
         "label": LABEL,
         "connected": bool(cfg.get("refresh_token")),
         "account": cfg.get("account", ""),
         "enabled": bool(cfg.get("enabled")),
         "enabled_at": cfg.get("enabled_at"),
         "interval_seconds": POLL_SECONDS,
         "gmail_scope": GOOGLE_SCOPE,
         "read_only": True}


class GmailConfig(BaseModel):
 client_id: str = Field(default="", max_length=220)
 client_secret: str = Field(default="", max_length=300)
 redirect_uri: str = Field(default="", max_length=500)
 enabled: bool = False


def _validate_uri(uri):
 u = urllib.parse.urlsplit(uri)
 return (u.scheme == "https" and bool(u.hostname) and u.port in (None, 443)
         and not u.username and not u.password
         and u.path == CALLBACK_PATH and not u.query and not u.fragment)


def upgrade(db_path, data_path):
 with sqlite3.connect(db_path) as c:
  c.execute("PRAGMA foreign_keys=ON")
  c.executescript("""
    CREATE TABLE IF NOT EXISTS gmail_auto_imports(
      gmail_id TEXT PRIMARY KEY,
      thread_id TEXT,
      source_digest TEXT,
      status TEXT NOT NULL DEFAULT 'processing',
      attempts INTEGER NOT NULL DEFAULT 0,
      created INTEGER NOT NULL DEFAULT 0,
      duplicates INTEGER NOT NULL DEFAULT 0,
      last_attempt INTEGER NOT NULL DEFAULT 0,
      completed_at TEXT,
      error TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_gmail_imports_digest
      ON gmail_auto_imports(source_digest);
    CREATE TABLE IF NOT EXISTS gmail_auto_tasks(
      fingerprint TEXT PRIMARY KEY,
      gmail_id TEXT NOT NULL REFERENCES gmail_auto_imports(gmail_id),
      task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
  """)


def _opener():
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self, request, response, status, msg, headers, newurl):
   return None
 return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def _json_request(url, *, data=None, token=None):
 # URLs are constructed only by trusted server-side code, never from an email.
 headers = {"Accept": "application/json", "User-Agent": "NextDo/0.1.25"}
 if data is not None:
  headers["Content-Type"] = "application/x-www-form-urlencoded"
 if token:
  headers["Authorization"] = "Bearer " + token
 req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
 try:
  with _opener().open(req, timeout=25) as response:
   raw = response.read(9_000_000)
  result = json.loads(raw)
  if not isinstance(result, dict):
   raise ValueError("JSON structure")
  return result
 except urllib.error.HTTPError as exc:
  if exc.code in (401, 403):
   fail("Google ha rifiutato l'accesso (HTTP " + str(exc.code) + "). Ricollegare l'account Gmail.", 502)
  if exc.code == 429:
   fail("Limite temporaneo delle API Gmail; il controllo verrà ripetuto", 502)
  fail("Google API HTTP " + str(exc.code), 502)
 except (OSError, ValueError, TimeoutError):
  fail("Collegamento alle API Google non riuscito", 502)


def _exchange(cfg, fields):
 data = urllib.parse.urlencode({
  "client_id": cfg["client_id"],
  "client_secret": cfg["client_secret"],
  **fields
 }).encode("utf-8")
 return _json_request("https://oauth2.googleapis.com/token", data=data)


def _access_token(cfg):
 refresh = cfg.get("refresh_token", "")
 if not refresh:
  fail("Collegare prima Gmail tramite Google OAuth")
 digest = hashlib.sha256(refresh.encode()).hexdigest()
 with TOKEN_LOCK:
  if (ACCESS_CACHE["refresh_id"] == digest and ACCESS_CACHE["expires"] > time.time() + 60
      and ACCESS_CACHE["value"]):
   return ACCESS_CACHE["value"]
  payload = _exchange(cfg, {"refresh_token": refresh, "grant_type": "refresh_token"})
  access = payload.get("access_token", "")
  if not isinstance(access, str) or not access:
   fail("Google non ha restituito un token di accesso; ricollegare Gmail", 502)
  ACCESS_CACHE.update(value=access, refresh_id=digest,
                      expires=time.time() + max(60, int(payload.get("expires_in", 3600))))
  return access


def _gmail_get(token, endpoint, params=None):
 query = urllib.parse.urlencode(params or {})
 url = "https://gmail.googleapis.com/gmail/v1/users/me/" + endpoint
 if query:
  url += "?" + query
 return _json_request(url, token=token)


def _list_ids(token, enabled_at=None):
 labels = _gmail_get(token, "labels").get("labels", [])
 match = next((item.get("id") for item in labels
               if isinstance(item, dict) and item.get("name") == LABEL), None)
 if not match:
  fail("Etichetta Gmail NextDo non trovata. Verificare il filtro Gmail.", 400)
 ids = []
 page = None
 for _ in range(MAX_PAGES):
  query = {"labelIds": match, "maxResults": 100}
  if enabled_at:
   query["q"] = "after:" + datetime.fromtimestamp(enabled_at / 1000, timezone.utc).strftime("%Y/%m/%d")
  if page:
   query["pageToken"] = page
  result = _gmail_get(token, "messages", query)
  ids.extend(item.get("id") for item in result.get("messages", [])
             if isinstance(item, dict) and isinstance(item.get("id"), str))
  page = result.get("nextPageToken")
  if not page:
   break
 return match, ids


def _reservation(conn, gmail_id, thread_id, *, force=False):
 with conn() as db:
  row = db.execute("SELECT status, attempts, last_attempt FROM gmail_auto_imports WHERE gmail_id=?",
                   (gmail_id,)).fetchone()
  if row:
   if row["status"] in ("processed", "duplicate", "ignored", "skipped"):
    return False
   if row["attempts"] >= 3 and not force:
    return False
   if row["status"] == "processing" and millis() - row["last_attempt"] < 600000 and not force:
    return False
   if row["status"] == "error" and millis() - row["last_attempt"] < POLL_SECONDS * 1000 and not force:
    return False
   db.execute("UPDATE gmail_auto_imports SET attempts=attempts+1,last_attempt=?,status='processing',error=NULL WHERE gmail_id=?",
              (millis(), gmail_id))
  else:
   db.execute("INSERT INTO gmail_auto_imports(gmail_id,thread_id,status,attempts,last_attempt) VALUES(?,?,'processing',1,?)",
              (gmail_id, thread_id, millis()))
 return True


def _mark(conn, gmail_id, status, reason=None, digest=None):
 with conn() as db:
  db.execute("UPDATE gmail_auto_imports SET status=?,error=?,source_digest=COALESCE(?,source_digest),completed_at=? WHERE gmail_id=?",
             (status, reason, digest, utc(), gmail_id))


def _one(conn, cfg, gmail_id, token, label_id):
 if not _reservation(conn, gmail_id, ""):
  return "existing", 0
 try:
  payload = _gmail_get(token, "messages/" + urllib.parse.quote(gmail_id, safe=""),
                       {"format": "raw"})
  if label_id not in payload.get("labelIds", []):
   _mark(conn, gmail_id, "ignored", "Etichetta non presente sul messaggio")
   return "ignored", 0
  if int(payload.get("internalDate", "0")) < int(cfg["enabled_at"]):
   _mark(conn, gmail_id, "ignored", "Messaggio precedente all'attivazione")
   return "ignored", 0
  raw = payload.get("raw")
  if not isinstance(raw, str) or len(raw) > 8_000_000:
   _mark(conn, gmail_id, "skipped", "Messaggio troppo grande")
   return "skipped", 0
  try:
   content = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
   source = email_intake.parse_mail(content)
  except HTTPException:
   _mark(conn, gmail_id, "skipped", "Messaggio non analizzabile")
   return "skipped", 0
  digest = hashlib.sha256((source["subject"].strip().casefold() + "\n" +
                            source["text"].strip().casefold()).encode("utf-8")).hexdigest()
  with conn() as db:
   duplicate = db.execute(
    "SELECT 1 FROM gmail_auto_imports WHERE source_digest=? AND gmail_id<>? AND status IN ('processed','duplicate') LIMIT 1",
    (digest, gmail_id)).fetchone()
  if duplicate:
   _mark(conn, gmail_id, "duplicate", "Contenuto già acquisito", digest)
   return "duplicate", 0
  proposals = email_intake.analyze(email_intake.load_config(cfg["data_path"]), source)["proposals"]
  created, duplicates = 0, 0
  with conn() as db:
   for item in proposals:
    title = item["title"]
    evidence = item["evidence"]
    due = item.get("due_date") or None  # YYYY-MM-DD; no artificial hour.
    fingerprint = hashlib.sha256((title.strip().casefold()+"\n"+(due or "")+"\n"+
                                  evidence.strip().casefold()).encode("utf-8")).hexdigest()
    if db.execute("SELECT 1 FROM gmail_auto_tasks WHERE fingerprint=?", (fingerprint,)).fetchone():
     duplicates += 1
     continue
    description = (
     "DA VERIFICARE - scadenza proposta automaticamente da email, non convalidata.\n"
     "Origine: Gmail, etichetta NextDo\n"
     "ID messaggio Gmail: "+gmail_id+"\n"
     "ID di tracciamento: "+digest+"\n"
     "Mittente: "+source["sender"]+"\n"
     "Oggetto: "+source["subject"]+"\n"
     "Data email: "+source["date"]+"\n"
     "Frase originale: "+evidence+"\n"
     "Azione proposta: "+str(item.get("description", "")).split("Azione proposta: ")[-1][:500]+"\n"
     "Orario, responsabili e CdS: [DA VERIFICARE]."
    )
    cursor = db.execute(
     "INSERT INTO tasks(title,description,kind,priority,status,due_at,start_at,owner_id,"
     "assigned_to,group_id,completion_mode,display_enabled,recurrence,labels,scope,project_id)"
     " VALUES(?,?,'task','normal','review',?,NULL,?,NULL,NULL,'global',0,'none',?,'personal',NULL)",
     (title, description, due, cfg["owner_id"], json.dumps(["Gmail NextDo", "Da verificare"], ensure_ascii=False)))
    task_id = cursor.lastrowid
    db.execute("INSERT INTO gmail_auto_tasks(fingerprint,gmail_id,task_id) VALUES(?,?,?)",
               (fingerprint, gmail_id, task_id))
    db.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",
               (cfg["owner_id"], "gmail_auto_create_unverified", "task", task_id))
    created += 1
   db.execute("UPDATE gmail_auto_imports SET source_digest=?,thread_id=?,status='processed',"
              "created=?,duplicates=?,completed_at=?,error=NULL WHERE gmail_id=?",
              (digest, str(payload.get("threadId", ""))[:100], created, duplicates, utc(), gmail_id))
  return "processed", created
 except Exception as exc:
  # Never store raw message text, access tokens or remote error bodies in the log.
  safe = str(exc.detail) if isinstance(exc, HTTPException) else "Errore durante l'acquisizione"
  _mark(conn, gmail_id, "error", safe[:240])
  raise


def run_once(conn, data_path, *, force=False):
 if not RUN_LOCK.acquire(blocking=False):
  return {"busy": True, "created": 0, "processed": 0, "duplicates": 0}
 try:
  cfg = _read(data_path)
  if not cfg.get("enabled") or not cfg.get("refresh_token"):
   fail("Acquisizione Gmail non attiva: collegare Google e abilitare il controllo")
  cfg["data_path"] = data_path
  with conn() as db:
   owner = db.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",
                      (cfg.get("owner_id"),)).fetchone()
  if not owner:
   fail("Amministratore Gmail non più attivo. Ricollegare l'account.")
  token = _access_token(cfg)
  label_id, ids = _list_ids(token, cfg.get("enabled_at"))
  counters = {"busy": False, "created": 0, "processed": 0, "duplicates": 0, "errors": 0}
  for gmail_id in ids:
   if counters["processed"] >= BATCH_LIMIT:
    break
   try:
    state, count = _one(conn, cfg, gmail_id, token, label_id)
    if state in ("processed", "duplicate"):
     counters["processed"] += 1
    if state == "duplicate":
     counters["duplicates"] += 1
    counters["created"] += count
   except Exception:
    counters["errors"] += 1
    LOG.warning("NextDo Gmail ingestion could not process message; retry scheduled")
  return counters
 finally:
  RUN_LOCK.release()


def _background(conn, data_path):
 while True:
  time.sleep(POLL_SECONDS)
  try:
   cfg = _read(data_path)
   if cfg.get("enabled") and cfg.get("refresh_token"):
    run_once(conn, data_path)
  except Exception:
   LOG.warning("NextDo Gmail scheduled check did not complete; retry in five minutes")


def register_routes(app, *, conn, user, csrf, data_path):
 def admin(req):
  who = user(req)
  if who["role"] != "admin":
   fail("Solo un amministratore può gestire Gmail", 403)
  return who

 @app.on_event("startup")
 def start_gmail_worker():
  global WORKER_STARTED
  if not WORKER_STARTED:
   WORKER_STARTED = True
   threading.Thread(target=_background, args=(conn, data_path), daemon=True,
                    name="nextdo-gmail").start()

 @app.get("/api/gmail-auto/config")
 def get_config(req: Request):
  admin(req)
  return _public(_read(data_path))

 @app.post("/api/gmail-auto/config")
 def save_config(body: GmailConfig, req: Request):
  who = admin(req); csrf(req)
  current = _read(data_path)
  client_id = body.client_id.strip()
  redirect = body.redirect_uri.strip()
  secret = body.client_secret or current.get("client_secret", "")
  if client_id and not re.fullmatch(r"[A-Za-z0-9._-]{8,220}", client_id):
   fail("Client ID Google non valido")
  if redirect and not _validate_uri(redirect):
   fail("Indicare un redirect URI HTTPS terminante con " + CALLBACK_PATH)
  changed = (client_id != current.get("client_id", "") or
             redirect != current.get("redirect_uri", "") or
             secret != current.get("client_secret", ""))
  if body.enabled and (changed or not current.get("refresh_token")):
   fail("Salvare le credenziali e collegare Gmail prima di attivare il controllo")
  updated = {**current, "client_id": client_id, "client_secret": secret,
             "redirect_uri": redirect, "enabled": bool(body.enabled),
             "owner_id": current.get("owner_id") or who["id"]}
  if changed:
   updated.update(refresh_token="", account="", enabled=False, owner_id=who["id"])
   ACCESS_CACHE.update(value="", expires=0, refresh_id="")
  if body.enabled and not current.get("enabled"):
   updated["enabled_at"] = millis()
  _write(data_path, updated)
  return _public(updated)

 @app.post("/api/gmail-auto/connect")
 def connect(req: Request):
  who = admin(req); csrf(req)
  cfg = _read(data_path)
  if not cfg.get("client_id") or not cfg.get("client_secret") or not cfg.get("redirect_uri"):
   fail("Configurare Client ID, Client Secret e redirect URI in Impostazioni")
  state = secrets.token_urlsafe(32)
  verifier = secrets.token_urlsafe(64)
  challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
  pending = {"state_digest": hashlib.sha256(state.encode()).hexdigest(), "verifier": verifier,
             "created": int(time.time()), "owner_id": who["id"],
             "client_id": cfg["client_id"], "redirect_uri": cfg["redirect_uri"]}
  file = Path(data_path) / "gmail-oauth-pending.json"
  fd = os.open(file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
  with os.fdopen(fd, "w") as stream:
   json.dump(pending, stream)
  url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
   "response_type": "code", "client_id": cfg["client_id"],
   "redirect_uri": cfg["redirect_uri"], "scope": GOOGLE_SCOPE,
   "access_type": "offline", "prompt": "consent", "state": state,
   "code_challenge": challenge, "code_challenge_method": "S256"
  })
  return {"authorization_url": url}

 @app.get(CALLBACK_PATH)
 def callback(req: Request, code: str = "", state: str = "", error: str = ""):
  path = Path(data_path) / "gmail-oauth-pending.json"
  if not path.exists() or not state:
   fail("Collegamento Gmail scaduto. Ripetere da Impostazioni.", 400)
  try:
   pending = json.loads(path.read_text())
  except (OSError, ValueError):
   fail("Collegamento Gmail non valido", 400)
  if (int(time.time()) - int(pending.get("created", 0)) > 600 or
      not secrets.compare_digest(pending.get("state_digest", ""),
                                  hashlib.sha256(state.encode()).hexdigest())):
   fail("Verifica OAuth Gmail non riuscita", 403)
  path.unlink(missing_ok=True)  # One-time authorization state.
  if error or not code:
   fail("Autorizzazione Google non completata", 400)
  cfg = _read(data_path)
  if (cfg.get("client_id") != pending.get("client_id") or
      cfg.get("redirect_uri") != pending.get("redirect_uri")):
   fail("Configurazione Google modificata durante il collegamento", 409)
  with conn() as db:
   who = db.execute("SELECT id FROM users WHERE id=? AND active=1 AND role='admin'",
                    (pending["owner_id"],)).fetchone()
  if not who:
   fail("Amministratore non più autorizzato", 403)
  payload = _exchange(cfg, {
   "grant_type": "authorization_code", "code": code, "redirect_uri": cfg["redirect_uri"],
   "code_verifier": pending["verifier"]
  })
  scope = payload.get("scope", "")
  if scope and GOOGLE_SCOPE not in scope.split():
   fail("Google non ha concesso l'accesso in sola lettura a Gmail", 403)
  refresh = payload.get("refresh_token", "")
  if not isinstance(refresh, str) or not refresh:
   fail("Google non ha fornito un refresh token. Revocare l'accesso e ripetere il collegamento.", 400)
  access = payload.get("access_token", "")
  account = ""
  if access:
   try:
    account = str(_gmail_get(access, "profile").get("emailAddress", ""))[:254]
   except HTTPException:
    pass
  cfg.update(refresh_token=refresh, owner_id=pending["owner_id"],
             enabled=False, enabled_at=None, account=account)
  _write(data_path, cfg)
  ACCESS_CACHE.update(value="", expires=0, refresh_id="")
  return RedirectResponse(url="/?gmail=connected", status_code=303)

 @app.post("/api/gmail-auto/disconnect")
 def disconnect(req: Request):
  admin(req); csrf(req)
  cfg = _read(data_path)
  cfg.update(refresh_token="", enabled=False, account="", enabled_at=None)
  _write(data_path, cfg)
  ACCESS_CACHE.update(value="", expires=0, refresh_id="")
  return _public(cfg)

 @app.post("/api/gmail-auto/run")
 def manual_run(req: Request):
  admin(req); csrf(req)
  return run_once(conn, data_path, force=True)

 @app.get("/api/gmail-auto/history")
 def history(req: Request):
  admin(req)
  with conn() as db:
   rows = db.execute("SELECT gmail_id,status,attempts,created,duplicates,completed_at,error "
                     "FROM gmail_auto_imports ORDER BY last_attempt DESC LIMIT 40").fetchall()
  return [dict(r) for r in rows]
