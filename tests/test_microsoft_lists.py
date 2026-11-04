"""Microsoft Lists pilot: no real Microsoft network requests; synthetic tenants and users."""
import importlib
import json
import os
from pathlib import Path

from test_workspace import init,create_user,sign_in

TENANT="22222222-2222-4222-8222-222222222222"
CLIENT="33333333-3333-4333-8333-333333333333"
LIST="44444444-4444-4444-8444-444444444444"
SHARE="https://sample.sharepoint.com/:l:/s/PILOTTEAM/FAKE?e=example"
SITE="https://sample.sharepoint.com/sites/PILOTTEAM"

def conf():
 return {"tenant_id":TENANT,"client_id":CLIENT,"site_url":SHARE}

def test_config_saves_site_only_and_starts_readonly(tmp_path):
 c,h=init(tmp_path)
 assert c.get("/api/microsoft/config").json()["authenticated"] is False
 assert c.post("/api/microsoft/config",headers=h,json=conf()).json()["site_url"]==SITE
 settings=tmp_path/"microsoft-lists-pilot.json"
 assert settings.exists()
 assert (settings.stat().st_mode & 0o777)==0o600
 saved=json.loads(settings.read_text())
 assert saved["site_url"]==SITE
 assert saved["list_id"]==""
 assert "access_token" not in settings.read_text()
 assert "refresh_token" not in settings.read_text()
 assert c.get("/api/microsoft/config").json()["mode"]=="read_only_pilot"
 assert c.get("/api/microsoft/lists").status_code==401
 assert c.post("/api/microsoft/config",json=conf()).status_code==403
 c.close()

def test_site_validation_and_users_do_not_access_admin_connectors(tmp_path):
 c,h=init(tmp_path)
 for site in ["http://sample.sharepoint.com/sites/PILOTTEAM",
              "https://evil.example/sites/PILOTTEAM",
              "https://sample-my.sharepoint.com/sites/PILOTTEAM",
              "https://sample.sharepoint.com.evil.example/sites/PILOTTEAM",
              "https://sample.sharepoint.com/thisisnotasite"]:
  result=c.post("/api/microsoft/config",headers=h,json={**conf(),"site_url":site})
  assert result.status_code==400, (site,result.text)
 assert c.post("/api/microsoft/config",headers=h,json=conf()).status_code==200
 create_user(c,h,"alice")
 sign_in(c,h,"alice")
 assert c.get("/api/microsoft/config").status_code==403
 assert c.get("/api/microsoft/lists").status_code==403
 assert c.post("/api/microsoft/auth/start",headers=h).status_code==403
 assert c.post("/api/microsoft/auth/check",headers=h).status_code==403
 assert c.post("/api/microsoft/auth/disconnect",headers=h).status_code==403
 assert c.post("/api/microsoft/config",headers=h,json=conf()).status_code==403
 c.close()

def test_device_login_list_selection_and_inspection_without_mutations(tmp_path,monkeypatch):
 c,h=init(tmp_path)
 assert c.post("/api/microsoft/config",headers=h,json=conf()).status_code==200
 ms=importlib.import_module("app.microsoft_lists")
 requests=[]
 def fake_http(url,form=None,token=None):
  requests.append((url,form,token))
  if url.endswith("/devicecode"):
   assert form["scope"]=="https://graph.microsoft.com/Sites.Read.All"
   return 200,{"device_code":"synthetic-device","user_code":"FAKE-4321",
               "verification_uri":"https://microsoft.com/devicelogin","expires_in":900,"interval":5}
  if url.endswith("/token"):
   return 200,{"access_token":"synthetic-access-token","expires_in":3600}
  raise AssertionError("Unexpected external request: "+url)
 def fake_graph(path,token):
  assert token=="synthetic-access-token"
  if path.startswith("/sites/sample.sharepoint.com:/sites/PILOTTEAM"):
   return {"id":"sample.sharepoint.com,site-guid,web-guid","displayName":"Pilot","webUrl":SITE}
  if "/lists?" in path:
   return {"value":[{"id":LIST,"displayName":"Empty pilot",
                     "list":{"template":"genericList"},"webUrl":SITE+"/Lists/pilot"},
                    {"id":"NOT-AN-ITEM","displayName":"Document lib","documentLibrary":{}}]}
  if "/columns?" in path:
   return {"value":[{"name":"Title"},{"name":"NextDoID"}]}
  raise AssertionError("Unexpected Graph call: "+path)
 monkeypatch.setattr(ms,"_http_json",fake_http)
 monkeypatch.setattr(ms,"_graph",fake_graph)
 device=c.post("/api/microsoft/auth/start",headers=h)
 assert device.status_code==200,device.text
 assert device.json()["user_code"]=="FAKE-4321"
 assert c.get("/api/microsoft/config").json()["authenticated"] is False
 verify=c.post("/api/microsoft/auth/check",headers=h)
 assert verify.status_code==200 and verify.json()["status"]=="connected"
 assert c.get("/api/microsoft/config").json()["authenticated"] is True
 lists=c.get("/api/microsoft/lists")
 assert lists.status_code==200,lists.text
 assert len(lists.json()["lists"])==1
 assert c.post("/api/microsoft/list/select",headers=h,json={"list_id":"wrong"}).status_code==404
 assert c.post("/api/microsoft/list/select",headers=h,json={"list_id":LIST}).status_code==200
 inspected=c.get("/api/microsoft/list/inspect")
 assert inspected.status_code==200,inspected.text
 assert inspected.json()["read_only"] is True
 assert inspected.json()["ready_for_sync"] is False
 assert "NextDoStatus" in inspected.json()["needed_for_sync"]
 saved=(tmp_path/"microsoft-lists-pilot.json").read_text()
 assert "synthetic-access-token" not in saved
 assert "synthetic-device" not in saved
 assert len([req for req in requests if req[0].endswith("/token")])==1
 assert c.post("/api/microsoft/auth/disconnect",headers=h).status_code==200
 assert c.get("/api/microsoft/config").json()["authenticated"] is False
 c.close()
