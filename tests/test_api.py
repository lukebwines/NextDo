import importlib
import os
import sqlite3
import sys
from pathlib import Path

from argon2 import PasswordHasher
from fastapi.testclient import TestClient


def app_client(tmp_path):
    os.environ["NEXTDO_DATA"] = str(tmp_path)
    sys.modules.pop("app.main", None)
    module = importlib.import_module("app.main")
    client = TestClient(module.app)
    csrf = client.get("/api/csrf").json()["csrf"]
    return client, {"X-NextDo-CSRF": csrf}


def test_fresh_install_and_note(tmp_path):
    client, headers = app_client(tmp_path)
    assert client.get("/api/setup").json()["needs_setup"]
    token = (tmp_path / "setup-token").read_text().strip()
    body = {"username": "tester", "password": "passphrase at least 12", "setup_token": token}
    assert client.post("/api/setup", json={**body, "setup_token": "WRONG TOKEN LONG VALUE"}, headers=headers).status_code == 403
    assert client.post("/api/setup", json=body, headers=headers).status_code == 200
    assert not (tmp_path / "setup-token").exists()
    assert client.post("/api/login", json={"username": "tester", "password": body["password"]}, headers=headers).status_code == 200
    assert client.get("/api/tasks").json() == []
    assert client.post("/api/tasks", json={"title": "Example task", "kind": "task", "priority": "high"}, headers=headers).status_code == 200
    assert client.post("/api/tasks", json={"title": "Example note", "kind": "note"}, headers=headers).status_code == 200
    tasks = client.get("/api/tasks").json()
    assert len(tasks) == 2
    assert any(item["kind"] == "note" for item in tasks)
    proposal = client.post("/api/extract", json={"text": "Urgente il 15 novembre 2030"}, headers=headers).json()
    assert proposal["needs_confirmation"]


def test_upgrade_legacy_database_without_losing_tasks(tmp_path):
    db = sqlite3.connect(tmp_path / "nextdo.sqlite3")
    db.executescript("""
    CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user');
    CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires TEXT NOT NULL);
    CREATE TABLE groups(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
    CREATE TABLE membership(group_id INTEGER,user_id INTEGER,PRIMARY KEY(group_id,user_id));
    CREATE TABLE courses(id INTEGER PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,active INTEGER DEFAULT 1);
    CREATE TABLE tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',priority TEXT NOT NULL DEFAULT 'normal',status TEXT NOT NULL DEFAULT 'todo',due_at TEXT,owner_id INTEGER NOT NULL,group_id INTEGER,published INTEGER DEFAULT 0,completion_mode TEXT DEFAULT 'global');
    CREATE TABLE task_courses(task_id INTEGER,course_id INTEGER,done INTEGER DEFAULT 0,PRIMARY KEY(task_id,course_id));
    CREATE TABLE display_tokens(hash TEXT PRIMARY KEY,group_id INTEGER,revoked INTEGER NOT NULL DEFAULT 0);
    """)
    db.execute("INSERT INTO users(id,username,password,role) VALUES(1,'tester',?,'admin')", (PasswordHasher().hash("passphrase at least 12"),))
    db.execute("INSERT INTO groups(id,name) VALUES(1,'Test group')")
    db.execute("INSERT INTO membership(group_id,user_id) VALUES(1,1)")
    db.execute("INSERT INTO tasks(id,title,owner_id,group_id,published) VALUES(1,'Keep existing task',1,1,1)")
    db.commit()
    db.close()
    client, headers = app_client(tmp_path)
    assert (tmp_path / "nextdo-before-full-ui-migration.sqlite3").exists()
    assert client.post("/api/login", json={"username": "tester", "password": "passphrase at least 12"}, headers=headers).status_code == 200
    tasks = client.get("/api/tasks").json()
    assert len(tasks) == 1 and tasks[0]["title"] == "Keep existing task"
    assert tasks[0]["display_enabled"] == 1
    assert client.get("/api/groups").json()[0]["name"] == "Test group"
