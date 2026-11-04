"""Project-level colleague–CdS assignments, minimal export, and permissions.

All user, project and course data used here are synthetic.
"""
from test_workspace import init, create_user, create_course, sign_in


def test_one_project_assignment_applies_to_every_task_and_many_courses(tmp_path):
 client,headers=init(tmp_path)
 physical=create_course(client,headers,'MZ1')
 speech=create_course(client,headers,'MZ2')
 college=create_user(client,headers,'colleague')
 second=create_user(client,headers,'second')
 created=client.post('/api/projects',headers=headers,json={
  'title':'Synthetic quality project','scope':'independent',
  'responsibilities':[
   {'course_id':physical,'user_id':college},
   {'course_id':speech,'user_id':college},
   {'course_id':speech,'user_id':second}]})
 assert created.status_code==200, created.text
 pid=created.json()['id']
 project=next(p for p in client.get('/api/projects').json() if p['id']==pid)
 assert len(project['responsibilities'])==3
 assert college not in project['member_ids']  # responsibilities do not grant global editing
 tasks=[]
 for name in ['Synthetic report','Synthetic review']:
  r=client.post('/api/tasks',headers=headers,json={'title':name,'scope':'project','project_id':pid})
  assert r.status_code==200, r.text
  tasks.append(r.json()['id'])
 target=f'/api/projects/{pid}/sharepoint-export'
 a=client.get(target)
 b=client.get(target)
 assert a.status_code==b.status_code==200
 assert a.json()==b.json()
 exported=a.json()['tasks']
 assert len(exported)==4
 assert {t['id'] for t in exported}=={
  f'NEXTDO-T{tid}-C{cid}' for tid in tasks for cid in (physical,speech)}
 assert {t['course_code'] for t in exported}=={'MZ1','MZ2'}
 assert all('responsible_user_ids' in t for t in exported)
 assert all(len(t['responsible_user_ids'])==1 for t in exported if t['course_code']=='MZ1')
 assert all(len(t['responsible_user_ids'])==2 for t in exported if t['course_code']=='MZ2')
 assert 'colleague' not in a.text and 'second' not in a.text
 sign_in(client,headers,'colleague')
 own=client.get('/api/projects')
 assert any(p['id']==pid for p in own.json())
 assert client.get(f'/api/projects/{pid}/sharepoint-export').status_code==403
 viewed=client.get(f'/api/tasks/{tasks[0]}')
 assert viewed.status_code==200
 assert viewed.json()['can_edit'] is False
 sign_in(client,headers,'admin')
 client.close()


def test_project_assignment_update_keeps_stable_ids_and_does_not_change_task(tmp_path):
 client,headers=init(tmp_path)
 c1=create_course(client,headers,'MZ1')
 c2=create_course(client,headers,'MZ2')
 uid=create_user(client,headers,'colleague')
 p=client.post('/api/projects',headers=headers,json={
  'title':'Synthetic project','scope':'independent',
  'responsibilities':[{'course_id':c1,'user_id':uid}]})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 t=client.post('/api/tasks',headers=headers,json={'title':'Original title','scope':'project','project_id':pid})
 tid=t.json()['id']
 before=client.get(f'/api/tasks/{tid}').json()
 old_export=client.get(f'/api/projects/{pid}/sharepoint-export').json()['tasks']
 assert [r['id'] for r in old_export]==[f'NEXTDO-T{tid}-C{c1}']
 updated=client.put(f'/api/projects/{pid}',headers=headers,json={
  'title':'Renamed project','scope':'independent',
  'responsibilities':[
   {'course_id':c1,'user_id':uid},
   {'course_id':c2,'user_id':uid}]})
 assert updated.status_code==200,updated.text
 new_export=client.get(f'/api/projects/{pid}/sharepoint-export').json()['tasks']
 assert {r['id'] for r in new_export}=={f'NEXTDO-T{tid}-C{c1}',f'NEXTDO-T{tid}-C{c2}'}
 assert all(r['title']==before['title'] for r in new_export)
 assert client.get(f'/api/tasks/{tid}').json()['id']==tid
 client.close()


def test_invalid_assignments_rejected_and_new_table_survives_restart(tmp_path):
 client,headers=init(tmp_path)
 a=create_course(client,headers,'MZ1')
 b=create_course(client,headers,'MZ2')
 person=create_user(client,headers,'colleague')
 original={'title':'Synthetic','scope':'independent'}
 duplicates={**original,'responsibilities':[{'course_id':a,'user_id':person}]*2}
 assert client.post('/api/projects',headers=headers,json=duplicates).status_code==400
 missing={**original,'responsibilities':[{'course_id':99999,'user_id':person}]}
 assert client.post('/api/projects',headers=headers,json=missing).status_code==400
 scoped={'title':'Scoped','scope':'cds','course_ids':[a],
         'responsibilities':[{'course_id':b,'user_id':person}]}
 assert client.post('/api/projects',headers=headers,json=scoped).status_code==400
 valid={**original,'responsibilities':[{'course_id':a,'user_id':person}]}
 r=client.post('/api/projects',headers=headers,json=valid)
 assert r.status_code==200,r.text
 pid=r.json()['id']
 assert (tmp_path/'nextdo-before-project-responsibilities-migration.sqlite3').exists()
 client.close()
 # Restart the application module without recreating the first administrator.
 import importlib,sys
 from fastapi.testclient import TestClient
 sys.modules.pop('app.main',None)
 mod=importlib.import_module('app.main')
 other=TestClient(mod.app)
 h={'X-NextDo-CSRF':other.get('/api/csrf').json()['csrf']}
 assert other.post('/api/login',headers=h,json={
  'username':'admin','password':'sample admin password 123'}).status_code==200
 assert any(p['id']==pid and p['responsibilities']==[
  {'course_id':a,'user_id':person}] for p in other.get('/api/projects').json())
 other.close()


def test_legacy_projects_keep_previous_json_shape(tmp_path):
 client,headers=init(tmp_path)
 p=client.post('/api/projects',headers=headers,json={
  'title':'Legacy project','scope':'independent'})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 t=client.post('/api/tasks',headers=headers,json={
  'title':'Legacy task','scope':'project','project_id':pid})
 assert t.status_code==200,t.text
 result=client.get(f'/api/projects/{pid}/sharepoint-export')
 assert result.status_code==200,result.text
 assert result.json()['tasks']==[{
  'id':f"NEXTDO-T{t.json()['id']}",'title':'Legacy task','status':'todo','due_at':None}]
 client.close()
