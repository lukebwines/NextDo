"""Workspace permissions and shared-deadline behavior, using synthetic users and CdS only."""
import importlib,os,sys
from fastapi.testclient import TestClient

def init(tmp_path):
 os.environ['NEXTDO_DATA']=str(tmp_path)
 sys.modules.pop('app.main',None)
 mod=importlib.import_module('app.main')
 client=TestClient(mod.app)
 csrf={'X-NextDo-CSRF':client.get('/api/csrf').json()['csrf']}
 credentials={'username':'admin','password':'sample admin password 123'}
 setup={**credentials,'setup_token':(tmp_path/'setup-token').read_text()}
 assert client.post('/api/setup',headers=csrf,json=setup).status_code==200
 assert client.post('/api/login',headers=csrf,json=credentials).status_code==200
 return client,csrf

def sign_in(client,headers,name):
 client.cookies.delete('nextdo_session')
 response=client.post('/api/login',headers=headers,json={'username':name,'password':'sample admin password 123' if name=='admin' else 'sample user password 123'})
 assert response.status_code==200,response.text

def create_user(client,headers,name):
 r=client.post('/api/users',headers=headers,json={'username':name,'display_name':name,'password':'sample user password 123','role':'user'})
 assert r.status_code==200,r.text
 users=client.get('/api/users').json()
 return next(u['id'] for u in users if u['username']==name)

def create_course(client,headers,code):
 r=client.post('/api/courses',headers=headers,json={'code':code,'name':'Test course '+code,'active':True})
 assert r.status_code==200,r.text
 return r.json()['id']

def test_cds_assignments_private_notes_and_common_completion(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob')
 a=create_course(c,h,'MZ1');b=create_course(c,h,'MZ2')
 assert c.put(f'/api/courses/{a}/assignees',headers=h,json={'user_ids':[alice]}).status_code==200
 assert c.put(f'/api/courses/{b}/assignees',headers=h,json={'user_ids':[bob]}).status_code==200
 task_a=c.post('/api/tasks',headers=h,json={'title':'Course A deadline','scope':'cds','course_ids':[a]})
 task_b=c.post('/api/tasks',headers=h,json={'title':'Course B deadline','scope':'cds','course_ids':[b]})
 assert task_a.status_code==200 and task_b.status_code==200
 aid,bid=task_a.json()['id'],task_b.json()['id']
 common=c.post('/api/tasks',headers=h,json={'title':'Common deadline','scope':'common','completion_mode':'per_course'})
 assert common.status_code==200,common.text
 cid=common.json()['id']
 single=c.post('/api/tasks',headers=h,json={'title':'Common global','scope':'common','completion_mode':'global'})
 assert single.status_code==200
 global_id=single.json()['id']
 sign_in(c,h,'alice')
 assert c.get('/api/my-courses').json()==[a]
 titles={t['title'] for t in c.get('/api/tasks').json()}
 assert 'Course A deadline' in titles and 'Course B deadline' not in titles and 'Common deadline' in titles
 assert c.get('/api/tasks/'+str(bid)).status_code==403
 assert c.patch(f'/api/tasks/{bid}/status',headers=h,json={'status':'done'}).status_code==403
 assert c.put(f'/api/courses/{a}/assignees',headers=h,json={'user_ids':[]}).status_code==403
 private=c.post('/api/tasks',headers=h,json={'title':'Private note','scope':'personal','kind':'note'})
 assert private.status_code==200
 private_id=private.json()['id']
 # A user cannot turn an assigned course activity into a private item.
 original=c.get('/api/tasks/'+str(aid)).json()
 changed={key:original[key] for key in ('title','description','kind','priority','status','due_at','assigned_to','group_id','completion_mode','display_enabled','recurrence','labels','reminders')}
 changed['scope']='personal';changed['project_id']=None;changed['course_ids']=[]
 assert c.put('/api/tasks/'+str(aid),headers=h,json=changed).status_code==403
 assert c.post(f'/api/tasks/{cid}/complete/{a}',headers=h).status_code==200
 assert c.post(f'/api/tasks/{cid}/complete/{b}',headers=h).status_code==403
 assert c.post(f'/api/tasks/{global_id}/toggle',headers=h).status_code==403
 sign_in(c,h,'bob')
 assert c.get('/api/tasks/'+str(private_id)).status_code==403
 assert c.get('/api/tasks/'+str(aid)).status_code==403
 assert c.post(f'/api/tasks/{cid}/complete/{b}',headers=h).status_code==200
 sign_in(c,h,'admin')
 assert c.get('/api/tasks/'+str(private_id)).status_code==403
 assert c.get('/api/tasks/'+str(cid)).json()['status']=='done'
 assert c.post(f'/api/tasks/{global_id}/toggle',headers=h).status_code==200
 c.close()

def test_projects_user_roles_and_password_management(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob')
 project=c.post('/api/projects',headers=h,json={'title':'Independent test project','scope':'independent','member_ids':[alice]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 assert c.post('/api/tasks',headers=h,json={'title':'Project task','scope':'project','project_id':pid,'assigned_to':alice}).status_code==200
 assert len(c.get('/api/projects').json())==1
 sign_in(c,h,'bob')
 assert c.get('/api/projects').json()==[]
 assert c.post('/api/projects',headers=h,json={'title':'Personal independent project','scope':'independent'}).status_code==200
 sign_in(c,h,'alice')
 assert any(p['id']==pid for p in c.get('/api/projects').json())
 tasks=c.get('/api/tasks').json()
 task=next(t for t in tasks if t['title']=='Project task')
 assert c.patch(f"/api/tasks/{task['id']}/status",headers=h,json={'status':'done'}).status_code==200
 changed=c.post('/api/profile/password',headers=h,json={'current_password':'sample user password 123','new_password':'new user password 456'})
 assert changed.status_code==200
 assert c.get('/api/profile').status_code==401
 old=c.post('/api/login',headers=h,json={'username':'alice','password':'sample user password 123'})
 assert old.status_code==401
 new=c.post('/api/login',headers=h,json={'username':'alice','password':'new user password 456'})
 assert new.status_code==200
 sign_in(c,h,'admin')
 denied=c.put('/api/admin/users/'+str(c.get('/api/me').json()['id']),headers=h,json={'role':'user','active':False})
 assert denied.status_code==400
 assert c.post(f'/api/admin/users/{bob}/password',headers=h,json={'new_password':'reset user password 789'}).status_code==200
 assert c.put(f'/api/admin/users/{bob}',headers=h,json={'role':'user','active':False}).status_code==200
 sign_in(c,h,'admin')
 assert c.get('/api/projects').status_code==200
 c.close()

def test_workspace_assets_and_sqlite_migration_are_idempotent(tmp_path):
 c,h=init(tmp_path)
 html=c.get('/').text
 assert 'assets/workspace-ui.js?v=' in html
 assert 'assets/workspace-ui.css?v=' in html
 assert html.index('workspace-ui.js')<html.index('assets/app.js')
 assert 'Assegna colleghi' in c.get('/assets/workspace-ui.js').text
 assert 'Il mio spazio' in c.get('/assets/app.js').text
 assert (tmp_path/'nextdo-before-workspaces-migration.sqlite3').exists()
 importlib.import_module('app.workspace').upgrade(tmp_path/'nextdo.sqlite3',tmp_path)
 assert c.get('/api/my-courses').status_code==200
 c.close()
