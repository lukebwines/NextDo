"""Dashboard Gantt and multiuser progress log: only synthetic task/account data."""
import sqlite3
from test_workspace import init,create_user,sign_in

def test_assigned_colleague_can_update_progress_and_admin_can_monitor(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice')
 bob=create_user(c,h,'bob')
 project=c.post('/api/projects',headers=h,json={'title':'Test project','scope':'independent','featured':True,'member_ids':[alice]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 obj=c.post('/api/tasks',headers=h,json={'title':'Draft example','kind':'task','scope':'project','project_id':pid,'assigned_to':alice})
 assert obj.status_code==200,obj.text
 tid=obj.json()['id']
 assert any(p['featured'] for p in c.get('/api/projects').json())
 sign_in(c,h,'bob')
 assert c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'doing','note':'Unauthorized'}).status_code==403
 assert c.get(f'/api/tasks/{tid}/progress').status_code==403
 sign_in(c,h,'alice')
 changed=c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'doing','note':'Bozza predisposta'})
 assert changed.status_code==200,changed.text
 assert c.get(f'/api/tasks/{tid}').json()['status']=='doing'
 assert c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'doing','note':'In attesa del riscontro'}).status_code==200
 assert c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'doing','note':''}).status_code==400
 events=c.get(f'/api/tasks/{tid}/progress')
 assert events.status_code==200
 assert len(events.json())==2
 assert events.json()[0]['actor']=='alice'
 assert events.json()[0]['note']=='In attesa del riscontro'
 sign_in(c,h,'admin')
 assert len(c.get(f'/api/tasks/{tid}/progress').json())==2
 assert c.get(f'/api/tasks/{tid}').json()['status']=='doing'
 c.close()

def test_featured_project_setting_and_existing_project_migration(tmp_path):
 c,h=init(tmp_path)
 project=c.post('/api/projects',headers=h,json={'title':'Featured first','scope':'independent','featured':True})
 assert project.status_code==200
 pid=project.json()['id']
 data={'title':'Do not feature','scope':'independent','featured':False,'status':'doing'}
 changed=c.put('/api/projects/'+str(pid),headers=h,json=data)
 assert changed.status_code==200,changed.text
 p=next(p for p in c.get('/api/projects').json() if p['id']==pid)
 assert p['featured']==0
 assert p['can_edit'] is True
 assert c.get('/assets/progress-ui.js').status_code==200
 page=c.get('/').text
 assert 'progress-ui.js?v=' in page and 'progress-ui.css?v=' in page
 assert page.index('progress-ui.js')<page.index('workspace-ui.js')
 assert (tmp_path/'nextdo-before-featured-projects-migration.sqlite3').exists()
 db=sqlite3.connect(tmp_path/'nextdo.sqlite3')
 assert 'featured' in {r[1] for r in db.execute('PRAGMA table_info(projects)')}
 assert 'task_progress' in {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
 db.close()
 c.close()

def test_progress_per_course_cannot_bypass_individual_completion(tmp_path):
 c,h=init(tmp_path)
 course=c.post('/api/courses',headers=h,json={'code':'MZ1','name':'Test CdS','active':True})
 assert course.status_code==200
 task=c.post('/api/tasks',headers=h,json={'title':'Common deadline','kind':'task','scope':'common','completion_mode':'per_course','status':'todo'})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 reject=c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'done','note':'Try bypass'})
 assert reject.status_code==400
 assert c.get(f'/api/tasks/{tid}').json()['status']=='todo'
 # Progress note with non-closing status is permitted, with audit history.
 assert c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'doing','note':'Planning'}).status_code==200
 assert c.post(f'/api/tasks/{tid}/complete/{course.json()["id"]}',headers=h).status_code==200
 assert c.get(f'/api/tasks/{tid}').json()['status']=='done'
 assert c.post(f'/api/tasks/{tid}/progress',headers=h,json={'status':'todo','note':'Try reopen without course'}).status_code==400
 c.close()
