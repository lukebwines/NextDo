"""Kanban permissions for colleagues working on shared and CdS projects.
All accounts and CdS below are synthetic fixtures.
"""
from test_workspace import init,create_user,create_course,sign_in

def test_member_may_drag_unassigned_task_but_not_another_colleagues_task(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice')
 bob=create_user(c,h,'bob')
 outsider=create_user(c,h,'outsider')
 p=c.post('/api/projects',headers=h,json={
   'title':'Team workflow','scope':'independent','member_ids':[alice,bob]})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 a=c.post('/api/tasks',headers=h,json={
   'title':'Unassigned work','scope':'project','project_id':pid})
 b=c.post('/api/tasks',headers=h,json={
   'title':'Bob work','scope':'project','project_id':pid,'assigned_to':bob})
 assert a.status_code==200 and b.status_code==200
 aid,bid=a.json()['id'],b.json()['id']
 sign_in(c,h,'alice')
 d=c.get(f'/api/tasks/{aid}').json()
 assert d['can_edit'] is False
 assert d['can_move'] is True
 assert d['can_complete'] is True
 assert c.patch(f'/api/tasks/{aid}/status',headers=h,json={'status':'doing'}).status_code==200
 # A colleague may report progress on unassigned work, without full edit rights.
 assert c.post(f'/api/tasks/{aid}/progress',headers=h,json={
  'status':'waiting','note':'Waiting for review'}).status_code==200
 assert c.get(f'/api/tasks/{aid}').json()['status']=='waiting'
 assert c.get(f'/api/tasks/{bid}').json()['can_move'] is False
 assert c.patch(f'/api/tasks/{bid}/status',headers=h,json={'status':'doing'}).status_code==403
 assert c.post(f'/api/tasks/{bid}/progress',headers=h,json={
  'status':'doing','note':'Trying to take colleague work'}).status_code==403
 sign_in(c,h,'bob')
 assert c.get(f'/api/tasks/{bid}').json()['can_move'] is True
 assert c.patch(f'/api/tasks/{bid}/status',headers=h,json={'status':'doing'}).status_code==200
 sign_in(c,h,'outsider')
 assert c.get(f'/api/tasks/{aid}').status_code==403
 assert c.patch(f'/api/tasks/{aid}/status',headers=h,json={'status':'done'}).status_code==403
 c.close()

def test_cds_assigned_colleague_can_advance_unassigned_project_tasks(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice')
 outsider=create_user(c,h,'outsider')
 course=create_course(c,h,'MZ1')
 assert c.put(f'/api/courses/{course}/assignees',headers=h,json={'user_ids':[alice]}).status_code==200
 p=c.post('/api/projects',headers=h,json={
   'title':'SMA pilot project','scope':'cds','course_ids':[course]})
 assert p.status_code==200,p.text
 tid=c.post('/api/tasks',headers=h,json={
   'title':'Prepare evidence','scope':'project','project_id':p.json()['id']}).json()['id']
 sign_in(c,h,'alice')
 t=c.get(f'/api/tasks/{tid}').json()
 assert t['can_move'] is True and t['can_edit'] is False
 assert c.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'doing'}).status_code==200
 sign_in(c,h,'outsider')
 assert c.get(f'/api/tasks/{tid}').status_code==403
 c.close()

def test_project_manager_may_move_assigned_task_and_per_cds_completion_is_protected(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice')
 bob=create_user(c,h,'bob')
 p=c.post('/api/projects',headers=h,json={
  'title':'Coordinated tasks','scope':'independent','manager_id':alice,'member_ids':[bob]})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 tid=c.post('/api/tasks',headers=h,json={
  'title':'Assigned to Bob','scope':'project','project_id':pid,'assigned_to':bob}).json()['id']
 sign_in(c,h,'alice')
 assert c.get(f'/api/tasks/{tid}').json()['can_move'] is True
 assert c.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'doing'}).status_code==200
 sign_in(c,h,'admin')
 course=create_course(c,h,'MZ1')
 common=c.post('/api/tasks',headers=h,json={
  'title':'Common per CdS','scope':'common','completion_mode':'per_course'})
 assert common.status_code==200
 cid=common.json()['id']
 assert c.patch(f'/api/tasks/{cid}/status',headers=h,json={'status':'done'}).status_code==400
 assert c.post(f'/api/tasks/{cid}/complete/{course}',headers=h).status_code==200
 assert c.get(f'/api/tasks/{cid}').json()['status']=='done'
 assert c.patch(f'/api/tasks/{cid}/status',headers=h,json={'status':'doing'}).status_code==400
 c.close()
