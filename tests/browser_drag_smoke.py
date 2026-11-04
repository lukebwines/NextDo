"""Real Chromium mouse drag test for NextDo Kanban permissions.

Runs only with Playwright installed. Uses a temporary database and synthetic
users; does not touch the Home Assistant installation or real user records.
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'nextdo'))

def check(response):
 assert response.status_code==200, (response.status_code,response.text)
 return response.json()

def main():
 from fastapi.testclient import TestClient
 from playwright.sync_api import sync_playwright
 with tempfile.TemporaryDirectory() as directory:
  os.environ['NEXTDO_DATA']=directory
  from app import main as appmod
  client=TestClient(appmod.app)
  headers={'X-NextDo-CSRF':check(client.get('/api/csrf'))['csrf']}
  token=(Path(directory)/'setup-token').read_text()
  check(client.post('/api/setup',headers=headers,json={
   'username':'admin','display_name':'Test administrator',
   'password':'synthetic admin password 123','setup_token':token}))
  check(client.post('/api/login',headers=headers,json={
   'username':'admin','password':'synthetic admin password 123'}))
  check(client.post('/api/users',headers=headers,json={
   'username':'alice','display_name':'Test colleague Alice',
   'role':'user','password':'synthetic colleague password 123'}))
  check(client.post('/api/users',headers=headers,json={
   'username':'bob','display_name':'Test colleague Bob',
   'role':'user','password':'synthetic colleague password 123'}))
  users=check(client.get('/api/users'))
  ids={u['username']:u['id'] for u in users}
  project=check(client.post('/api/projects',headers=headers,json={
   'title':'Synthetic team project','scope':'independent',
   'member_ids':[ids['alice'],ids['bob']]}))
  pid=project['id']
  course_id=check(client.post('/api/courses',headers=headers,json={
   'code':'MZ01','name':'Synthetic course','active':True}))['id']
  check(client.post('/api/projects',headers=headers,json={
   'title':'Synthetic course project','scope':'cds',
   'course_ids':[course_id],'member_ids':[ids['alice']]}))
  unassigned=check(client.post('/api/tasks',headers=headers,json={
   'title':'Unassigned drag test','kind':'task','scope':'project','project_id':pid}))
  assigned=check(client.post('/api/tasks',headers=headers,json={
   'title':'Bob private assignment','kind':'task','scope':'project','project_id':pid,
   'assigned_to':ids['bob']}))
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
  base=f'http://127.0.0.1:{port}/'
  env=os.environ.copy()
  env['PYTHONPATH']=str(ROOT/'nextdo')
  server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app',
      '--host','127.0.0.1','--port',str(port),'--no-access-log'],
      env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  try:
   for _ in range(80):
    if server.poll() is not None:raise RuntimeError('NextDo server exited')
    try:
     with urlopen(base+'api/csrf',timeout=2) as resp:
      if resp.status==200:break
    except Exception:time.sleep(.15)
   else:raise RuntimeError('NextDo server failed to start')
   with sync_playwright() as play:
    browser=play.chromium.launch(headless=True)
    try:
     page=browser.new_page(viewport={'width':1365,'height':930})
     page.goto(base,wait_until='networkidle')
     page.locator('input[name="username"]').fill('alice')
     page.locator('input[name="password"]').fill('synthetic colleague password 123')
     page.get_by_role('button',name='Accedi').click()
     page.get_by_role('button',name='Progetti',exact=True).wait_for()
     page.get_by_role('button',name='Progetti',exact=True).click()
     assert page.locator('.project-list-row').count()==2,'Two projects must fit in the compact index'
     assert page.locator('.kanban-board').count()==0,'Kanban must open only within a project'
     page.get_by_label('Cerca progetti').fill('Synthetic team project')
     assert page.locator('.project-list-row').count()==1
     page.get_by_label('Cerca progetti').fill('')
     page.get_by_label('Filtra per CdS').select_option(str(course_id))
     assert page.locator('.project-list-row').count()==1
     assert 'Synthetic course project' in page.locator('.project-list-row').inner_text()
     page.get_by_label('Filtra per CdS').select_option('')
     page.get_by_role('button',name='Completati',exact=True).click()
     assert page.locator('.project-list-row').count()==0
     page.get_by_role('button',name='Attivi',exact=True).click()
     page.locator('.project-list-row',has_text='Synthetic team project').click()
     assert page.locator('.kanban-board').count()==1
     page.get_by_role('button',name='Torna ai progetti').click()
     assert page.locator('.project-list-row').count()==2
     assert page.locator('.kanban-board').count()==0
     page.locator('.project-list-row',has_text='Synthetic team project').click()
     card=page.locator('.kanban-task',has_text='Unassigned drag test')
     card.wait_for(timeout=10000)
     assert card.get_attribute('draggable')=='true','Team member must be able to drag unassigned card'
     readonly=page.locator('.kanban-task',has_text='Bob private assignment')
     assert readonly.get_attribute('draggable')=='false','Other colleague work must remain read-only'
     assert readonly.locator('.kanban-status-select').count()==0
     in_progress=page.locator('.kanban-col').nth(1)
     card.drag_to(in_progress,timeout=15000)
     page.wait_for_function("""() => {
       const columns=document.querySelectorAll('.kanban-col');
       return columns[1]?.textContent.includes('Unassigned drag test');
     }""",timeout=15000)
     assert check(client.get('/api/tasks/'+str(unassigned['id'])))['status']=='doing'
     moved=page.locator('.kanban-task',has_text='Unassigned drag test')
     moved.locator('.kanban-status-select').select_option('waiting')
     page.wait_for_function("""() => {
       const columns=document.querySelectorAll('.kanban-col');
       return columns[2]?.textContent.includes('Unassigned drag test');
     }""",timeout=15000)
     assert check(client.get('/api/tasks/'+str(unassigned['id'])))['status']=='waiting'
     assert check(client.get('/api/tasks/'+str(assigned['id'])))['status']=='todo'
     print('PASS: real Chromium drag-and-drop and status menu; team permissions enforced')
    finally:browser.close()
  finally:
   server.terminate()
   try:server.communicate(timeout=5)
   except subprocess.TimeoutExpired:
    server.kill();server.communicate()
   client.close()

if __name__=='__main__':main()
