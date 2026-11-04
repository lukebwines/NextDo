"""NextDo per-project SharePoint JSON export contract; synthetic data only."""
from test_workspace import init, create_user, sign_in


def test_export_is_stable_minimal_json_and_never_contains_private_data(tmp_path):
 client,h=init(tmp_path)
 p=client.post('/api/projects',headers=h,json={'title':'Synthetic pilot project','scope':'independent'})
 assert p.status_code==200,p.text
 pid=p.json()['id']
 task=client.post('/api/tasks',headers=h,json={
  'title':'Synthetic administrative task','description':'PRIVATE DESCRIPTION MUST NOT EXPORT',
  'scope':'project','project_id':pid,'status':'doing','due_at':'2026-11-13T12:00:00+01:00'})
 assert task.status_code==200,task.text
 tid=task.json()['id']
 assert client.post('/api/tasks',headers=h,json={'title':'Private note must not export','scope':'personal','kind':'note'}).status_code==200
 other=client.post('/api/projects',headers=h,json={'title':'Other project','scope':'independent'})
 assert other.status_code==200
 assert client.post('/api/tasks',headers=h,json={'title':'Other project must not export','scope':'project','project_id':other.json()['id']}).status_code==200
 url='/api/projects/'+str(pid)+'/sharepoint-export'
 first=client.get(url)
 second=client.get(url)
 assert first.status_code==second.status_code==200
 assert first.headers['content-type'].startswith('application/json')
 assert first.headers['cache-control'].startswith('no-store')
 assert 'attachment; filename="nextdo-project-'+str(pid)+'-' in first.headers['content-disposition']
 assert first.headers['content-disposition']!=second.headers['content-disposition']
 assert first.json()==second.json()
 data=first.json()
 assert data['schema_version']=='1.0' and data['source']=='NextDo'
 assert data['project']=={'id':'NEXTDO-P'+str(pid),'title':'Synthetic pilot project'}
 assert data['tasks']==[{
  'id':'NEXTDO-T'+str(tid),'title':'Synthetic administrative task',
  'status':'doing','due_at':'2026-11-13T12:00:00+01:00'
 }]
 assert 'PRIVATE DESCRIPTION MUST NOT EXPORT' not in first.text
 assert 'Private note' not in first.text
 assert 'Other project' not in first.text
 assert client.get('/api/projects/999999/sharepoint-export').status_code==404
 client.close()


def test_export_is_restricted_to_project_managers_and_admins(tmp_path):
 client,h=init(tmp_path)
 manager=create_user(client,h,'manager')
 member=create_user(client,h,'member')
 outside=create_user(client,h,'outside')
 project=client.post('/api/projects',headers=h,json={
  'title':'Synthetic shared project','scope':'independent','manager_id':manager,
  'member_ids':[manager,member]})
 assert project.status_code==200,project.text
 pid=project.json()['id']
 task=client.post('/api/tasks',headers=h,json={
  'title':'Synthetic project activity','scope':'project','project_id':pid,
  'assigned_to':member})
 assert task.status_code==200,task.text
 url=f'/api/projects/{pid}/sharepoint-export'
 assert client.get(url).status_code==200
 sign_in(client,h,'member')
 assert any(x['id']==pid for x in client.get('/api/projects').json())
 assert client.get(url).status_code==403
 sign_in(client,h,'outside')
 assert client.get(url).status_code==403
 sign_in(client,h,'manager')
 assert client.get(url).status_code==200
 client.cookies.delete('nextdo_session')
 assert client.get(url).status_code==401
 client.close()


def test_empty_project_export_and_ui_button(tmp_path):
 client,h=init(tmp_path)
 p=client.post('/api/projects',headers=h,json={'title':'Empty synthetic project','scope':'independent'})
 assert p.status_code==200
 data=client.get(f"/api/projects/{p.json()['id']}/sharepoint-export").json()
 assert data['tasks']==[]
 script=client.get('/assets/workspace-ui.js')
 assert script.status_code==200
 assert 'Esporta JSON per Lists' in script.text
 assert 'sharepoint-export' in script.text
 client.close()
