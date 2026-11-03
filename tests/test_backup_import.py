"""Backup import tests use only dummy data, never course registries."""
import importlib,io,os,sys,zipfile
from fastapi.testclient import TestClient

def client(tmp_path):
 os.environ['NEXTDO_DATA']=str(tmp_path)
 sys.modules.pop('app.main',None)
 mod=importlib.import_module('app.main')
 c=TestClient(mod.app)
 h={'X-NextDo-CSRF':c.get('/api/csrf').json()['csrf']}
 creds={'username':'tester','password':'passphrase at least 12'}
 setup=dict(creds,setup_token=(tmp_path/'setup-token').read_text())
 assert c.post('/api/setup',headers=h,json=setup).status_code==200
 assert c.post('/api/login',headers=h,json=creds).status_code==200
 return c,h,creds

def upload(c,h,raw,confirm='RIPRISTINA'):
 return c.post('/api/backup/import',headers=h,data={'confirm':confirm},files={'file':('nextdo-backup.zip',raw,'application/zip')})

def test_restore_creates_snapshot_and_revokes_sessions(tmp_path):
 c,h,creds=client(tmp_path)
 assert c.post('/api/tasks',headers=h,json={'title':'Original'}).status_code==200
 saved=c.get('/api/backup').content
 assert c.post('/api/tasks',headers=h,json={'title':'To remove'}).status_code==200
 result=upload(c,h,saved)
 assert result.status_code==200,result.text
 assert (tmp_path/result.json()['pre_restore_backup']).is_file()
 assert c.get('/api/tasks').status_code==401
 assert c.post('/api/login',headers=h,json=creds).status_code==200
 titles=[t['title'] for t in c.get('/api/tasks').json()]
 assert titles==['Original']
 c.close()

def test_reject_zip_traversal_without_destroying_data(tmp_path):
 c,h,_=client(tmp_path)
 assert c.post('/api/tasks',headers=h,json={'title':'Keep'}).status_code==200
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  z.writestr('database.sqlite3',b'not a database')
  z.writestr('attachments/../../escape',b'x')
 assert upload(c,h,b.getvalue()).status_code==400
 assert c.get('/api/tasks').json()[0]['title']=='Keep'
 assert upload(c,h,c.get('/api/backup').content,'WRONG').status_code==400
 c.close()

def test_import_is_admin_only(tmp_path):
 c,h,_=client(tmp_path)
 assert c.post('/api/users',headers=h,json={'username':'second','display_name':'Second','password':'passphrase at least 12','role':'user'}).status_code==200
 c.post('/api/logout',headers=h)
 assert c.post('/api/login',headers=h,json={'username':'second','password':'passphrase at least 12'}).status_code==200
 assert upload(c,h,b'not zip').status_code==403
 c.close()
