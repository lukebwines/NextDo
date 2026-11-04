"""Project Gantt tests with synthetic tasks; no real user/course data."""
import importlib
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from test_workspace import init,create_user,sign_in

def test_gantt_start_and_deadline_are_persisted_and_validated(tmp_path):
 c,h=init(tmp_path)
 p=c.post('/api/projects',headers=h,json={'title':'Synthetic workflow','scope':'independent'})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 base={'title':'Prepare document','kind':'task','scope':'project','project_id':pid}
 start='2026-11-04T09:00:00+01:00'
 due='2026-11-12T18:00:00+01:00'
 created=c.post('/api/tasks',headers=h,json={**base,'start_at':start,'due_at':due})
 assert created.status_code==200,created.text
 tid=created.json()['id']
 task=c.get(f'/api/tasks/{tid}').json()
 assert task['start_at']==start and task['due_at']==due
 assert task['project_id']==pid
 assert task['can_edit'] is True
 assert c.post('/api/tasks',headers=h,json={**base,'title':'Invalid dates','start_at':due,'due_at':start}).status_code==400
 assert c.post('/api/tasks',headers=h,json={**base,'title':'Invalid date input','start_at':'not-a-date','due_at':due}).status_code in (400,422)
 # One date is valid (milestone); no dates is valid (backlog).
 milestone=c.post('/api/tasks',headers=h,json={**base,'title':'Milestone','due_at':due})
 assert milestone.status_code==200,milestone.text
 assert c.get('/api/tasks/'+str(milestone.json()['id'])).json()['start_at'] is None
 backlog=c.post('/api/tasks',headers=h,json={**base,'title':'Unplanned task'})
 assert backlog.status_code==200
 update={key:task[key] for key in ('title','description','kind','priority','status','due_at','assigned_to','group_id','completion_mode','display_enabled','recurrence','labels','scope','project_id','reminders')}
 update['course_ids']=[course['id'] for course in task['courses']]
 update['start_at']='2026-11-05T09:00:00+01:00'
 changed=c.put('/api/tasks/'+str(tid),headers=h,json=update)
 assert changed.status_code==200,changed.text
 assert c.get('/api/tasks/'+str(tid)).json()['start_at']==update['start_at']
 c.close()

def test_gantt_project_permissions_remain_enforced(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob')
 project=c.post('/api/projects',headers=h,json={'title':'Private team project','scope':'independent','member_ids':[alice]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 task=c.post('/api/tasks',headers=h,json={'title':'Team schedule','scope':'project','project_id':pid,
     'assigned_to':alice,'start_at':'2026-11-05T08:00:00+01:00','due_at':'2026-11-10T18:00:00+01:00'})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 sign_in(c,h,'bob')
 assert c.get('/api/tasks/'+str(tid)).status_code==403
 assert not c.get('/api/projects').json()
 sign_in(c,h,'alice')
 assert c.get('/api/tasks/'+str(tid)).status_code==200
 assert c.get('/api/tasks/'+str(tid)).json()['can_edit'] is True
 c.close()

def test_gantt_assets_and_legacy_upgrade(tmp_path):
 c,h=init(tmp_path)
 homepage=c.get('/').text
 assert 'gantt.js?v=' in homepage
 assert 'gantt.css?v=' in homepage
 assert homepage.index('gantt.js')<homepage.index('workspace-ui.js')
 assert 'Cronoprogramma' in c.get('/assets/gantt.js').text
 assert (tmp_path/'nextdo-before-workspaces-migration.sqlite3').exists()
 c.close()
 # Simulate an existing NextDo 0.1.7 database with all previous task dates but no start_at column.
 dbpath=tmp_path/'legacy-gantt.sqlite3'
 db=sqlite3.connect(dbpath)
 with db:
  db.execute('CREATE TABLE tasks (id INTEGER PRIMARY KEY,scope TEXT,project_id INTEGER,due_at TEXT)')
  db.execute('INSERT INTO tasks(id,scope,project_id,due_at) VALUES (1,?,?,?)',('project',7,'2026-11-30T17:00:00+01:00'))
 db.close()
 workspaces=importlib.import_module('app.workspace')
 workspaces.upgrade(dbpath,tmp_path)
 backup=tmp_path/'nextdo-before-gantt-migration.sqlite3'
 assert backup.exists()
 connection=sqlite3.connect(dbpath)
 assert connection.execute('SELECT due_at,start_at FROM tasks WHERE id=1').fetchone()==('2026-11-30T17:00:00+01:00',None)
 connection.close()
 snapshot=backup.read_bytes()
 workspaces.upgrade(dbpath,tmp_path)
 assert backup.read_bytes()==snapshot
