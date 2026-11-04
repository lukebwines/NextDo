"""Kanban drag authorization for shared project teams; synthetic data only."""
from test_workspace import init,create_user,create_course,sign_in

def test_project_member_can_move_unassigned_task_but_not_colleague_task(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob');eve=create_user(c,h,'eve')
 project=c.post('/api/projects',headers=h,json={
  'title':'Synthetic team project','scope':'independent','member_ids':[alice,bob]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 free=c.post('/api/tasks',headers=h,json={'title':'Unassigned team task','scope':'project','project_id':pid})
 reserved=c.post('/api/tasks',headers=h,json={'title':'Assigned to Bob','scope':'project','project_id':pid,'assigned_to':bob})
 assert free.status_code==200 and reserved.status_code==200
 fid=free.json()['id'];rid=reserved.json()['id']
 sign_in(c,h,'alice')
 task=c.get(f'/api/tasks/{fid}').json()
 assert task['can_edit'] is True
 assert c.patch(f'/api/tasks/{fid}/status',headers=h,json={'status':'doing'}).status_code==200
 assert c.get(f'/api/tasks/{fid}').json()['status']=='doing'
 assert c.post(f'/api/tasks/{fid}/progress',headers=h,json={'status':'waiting','note':'In attesa di riscontro'}).status_code==200
 assert c.get(f'/api/tasks/{fid}').json()['status']=='waiting'
 assert c.get(f'/api/tasks/{rid}').json()['can_edit'] is False
 assert c.patch(f'/api/tasks/{rid}/status',headers=h,json={'status':'doing'}).status_code==403
 assert c.post(f'/api/tasks/{rid}/progress',headers=h,json={'status':'doing','note':'Non autorizzata'}).status_code==403
 sign_in(c,h,'eve')
 assert c.get(f'/api/tasks/{fid}').status_code==403
 assert c.patch(f'/api/tasks/{fid}/status',headers=h,json={'status':'done'}).status_code==403
 sign_in(c,h,'bob')
 assert c.get(f'/api/tasks/{rid}').json()['can_edit'] is True
 assert c.patch(f'/api/tasks/{rid}/status',headers=h,json={'status':'doing'}).status_code==200
 c.close()

def test_cds_colleague_can_advance_unassigned_project_work(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob')
 cid=create_course(c,h,'MZ1')
 assert c.put(f'/api/courses/{cid}/assignees',headers=h,json={'user_ids':[alice]}).status_code==200
 project=c.post('/api/projects',headers=h,json={'title':'Course project','scope':'cds','course_ids':[cid]})
 assert project.status_code==200,project.text
 task=c.post('/api/tasks',headers=h,json={'title':'Unassigned CdS project task','scope':'project','project_id':project.json()['id']})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 sign_in(c,h,'alice')
 assert c.get(f'/api/tasks/{tid}').json()['can_edit'] is True
 assert c.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'doing'}).status_code==200
 sign_in(c,h,'bob')
 assert c.get(f'/api/tasks/{tid}').status_code==403
 c.close()

def test_common_project_viewers_cannot_edit_without_membership(tmp_path):
 c,h=init(tmp_path)
 alice=create_user(c,h,'alice');bob=create_user(c,h,'bob')
 project=c.post('/api/projects',headers=h,json={
  'title':'Common read-only project','scope':'common','member_ids':[alice]})
 assert project.status_code==200,project.text
 task=c.post('/api/tasks',headers=h,json={'title':'Common project free task','scope':'project','project_id':project.json()['id']})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 sign_in(c,h,'bob')
 assert c.get(f'/api/tasks/{tid}').json()['can_edit'] is False
 assert c.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'doing'}).status_code==403
 sign_in(c,h,'alice')
 assert c.get(f'/api/tasks/{tid}').json()['can_edit'] is True
 assert c.patch(f'/api/tasks/{tid}/status',headers=h,json={'status':'doing'}).status_code==200
 c.close()
