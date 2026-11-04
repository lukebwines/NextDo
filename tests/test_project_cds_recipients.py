"""Per-CdS project assignment and SharePoint export tests. Synthetic data only."""
from test_workspace import init,create_user,create_course,sign_in


def full_task_payload(task):
 keys=('title','description','kind','priority','status','due_at','start_at',
       'assigned_to','group_id','completion_mode','display_enabled','recurrence',
       'labels','scope','project_id','reminders')
 return {key:task[key] for key in keys}


def test_project_task_exports_independent_rows_for_each_course(tmp_path):
 client,h=init(tmp_path)
 c1=create_course(client,h,'MZ1')
 c2=create_course(client,h,'MZ2')
 project=client.post('/api/projects',headers=h,json={
  'title':'Synthetic project','scope':'independent'})
 assert project.status_code==200
 pid=project.json()['id']
 created=client.post('/api/tasks',headers=h,json={
  'title':'Synthetic activity','description':'SECRET DESCRIPTION','scope':'project',
  'project_id':pid,'status':'doing','course_ids':[c2,c1]})
 assert created.status_code==200,created.text
 tid=created.json()['id']
 target=f'/api/projects/{pid}/sharepoint-export'
 one=client.get(target)
 two=client.get(target)
 assert one.status_code==two.status_code==200
 assert one.json()==two.json()
 tasks=one.json()['tasks']
 assert [t['id'] for t in tasks]==[f'NEXTDO-T{tid}-C{c1}',f'NEXTDO-T{tid}-C{c2}']
 for t in tasks:
  assert t['title']=='Synthetic activity'
  assert t['status']=='doing'
  assert t['course_code'] in ('MZ1','MZ2')
  assert t['course_name']=='Test course '+t['course_code']
  assert t['project_title']=='Synthetic project'
  assert t['due_at'] is None
 assert 'SECRET DESCRIPTION' not in one.text
 assert client.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'done'}).status_code==200
 updated=client.get(target).json()['tasks']
 assert [t['id'] for t in updated]==[t['id'] for t in tasks]
 assert all(t['status']=='done' for t in updated)
 client.close()


def test_legacy_task_export_id_is_preserved_when_no_courses_assigned(tmp_path):
 client,h=init(tmp_path)
 c1=create_course(client,h,'MZ1')
 project=client.post('/api/projects',headers=h,json={'title':'Synthetic project','scope':'independent'})
 pid=project.json()['id']
 created=client.post('/api/tasks',headers=h,json={'title':'Old activity','scope':'project','project_id':pid})
 tid=created.json()['id']
 target=f'/api/projects/{pid}/sharepoint-export'
 original=client.get(target).json()['tasks']
 assert original==[{'id':f'NEXTDO-T{tid}','title':'Old activity','status':'todo','due_at':None}]
 payload=full_task_payload(client.get(f'/api/tasks/{tid}').json())
 payload['course_ids']=[c1]
 assert client.put(f'/api/tasks/{tid}',headers=h,json=payload).status_code==200
 now=client.get(target).json()['tasks']
 assert len(now)==1 and now[0]['id']==f'NEXTDO-T{tid}-C{c1}'
 client.close()


def test_project_recipient_permissions_and_nonmanager_task_edits(tmp_path):
 client,h=init(tmp_path)
 c1=create_course(client,h,'MZ1')
 c2=create_course(client,h,'MZ2')
 member=create_user(client,h,'member')
 manager=create_user(client,h,'manager')
 assert client.put(f'/api/courses/{c1}/assignees',headers=h,json={'user_ids':[manager]}).status_code==200
 project=client.post('/api/projects',headers=h,json={
  'title':'Synthetic shared project','scope':'independent',
  'manager_id':manager,'member_ids':[manager,member]})
 assert project.status_code==200
 pid=project.json()['id']
 task=client.post('/api/tasks',headers=h,json={
  'title':'Task','scope':'project','project_id':pid,'course_ids':[c2],
  'assigned_to':member})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 sign_in(client,h,'member')
 assert client.post('/api/tasks',headers=h,json={
  'title':'Unauthorized routing','scope':'project','project_id':pid,
  'course_ids':[c1]}).status_code==403
 payload=full_task_payload(client.get(f'/api/tasks/{tid}').json())
 payload['course_ids']=[c2]
 payload['title']='Editing without changing destinations'
 ok=client.put(f'/api/tasks/{tid}',headers=h,json=payload)
 assert ok.status_code==200,ok.text
 payload['course_ids']=[c1]
 assert client.put(f'/api/tasks/{tid}',headers=h,json=payload).status_code==403
 sign_in(client,h,'manager')
 manager_payload=full_task_payload(client.get(f'/api/tasks/{tid}').json())
 manager_payload['course_ids']=[c1]
 changed=client.put(f'/api/tasks/{tid}',headers=h,json=manager_payload)
 assert changed.status_code==200,changed.text
 manager_payload['course_ids']=[c1,c2]
 assert client.put(f'/api/tasks/{tid}',headers=h,json=manager_payload).status_code==403
 assert [t['id'] for t in client.get(f'/api/projects/{pid}/sharepoint-export').json()['tasks']]==[f'NEXTDO-T{tid}-C{c1}']
 client.close()


def test_course_scoped_project_cannot_export_to_unlinked_course(tmp_path):
 client,h=init(tmp_path)
 c1=create_course(client,h,'MZ1')
 c2=create_course(client,h,'MZ2')
 project=client.post('/api/projects',headers=h,json={
  'title':'Scoped project','scope':'cds','course_ids':[c1]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 bad=client.post('/api/tasks',headers=h,json={
  'title':'Out-of-scope assignment','scope':'project','project_id':pid,
  'course_ids':[c2]})
 assert bad.status_code==400,bad.text
 good=client.post('/api/tasks',headers=h,json={
  'title':'In-scope assignment','scope':'project','project_id':pid,
  'course_ids':[c1]})
 assert good.status_code==200,good.text
 client.close()


def test_task_form_has_course_destination_picker_and_project_switch(tmp_path):
 client,h=init(tmp_path)
 js=client.get('/assets/app.js')
 assert js.status_code==200
 assert "const courseWrap=el('div',{class:'full'},[courses.outer,recipientHelp]);" in js.text
 assert "project.addEventListener('change',updateScope);" in js.text
 assert "scope.value==='project'" in js.text
 kanban=client.get('/assets/workspace-ui.js')
 assert kanban.status_code==200
 assert 't.courses||[]' in kanban.text
 client.close()
