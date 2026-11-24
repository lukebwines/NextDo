"""Archive and storage regression tests, using synthetic documents only."""
import importlib,io,json,os,sqlite3,sys,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import load_workbook

def checked(r):
 assert r.status_code==200,r.text[:1000]
 return r.json()

def setup(tmp_path):
 os.environ['NEXTDO_DATA']=str(tmp_path)
 sys.modules.pop('app.main',None)
 mod=importlib.import_module('app.main')
 client=TestClient(mod.app)
 headers={'X-NextDo-CSRF':checked(client.get('/api/csrf'))['csrf']}
 cred={'username':'archive-admin','password':'synthetic long password'}
 checked(client.post('/api/setup',headers=headers,json={**cred,'setup_token':(tmp_path/'setup-token').read_text()}))
 checked(client.post('/api/login',headers=headers,json=cred))
 return mod,client,headers

def make(client,headers,title,status='todo',**kwargs):
 return checked(client.post('/api/tasks',headers=headers,json={'title':title,'status':status,**kwargs}))['id']

def attach(client,headers,tid,name='document.pdf',payload=b'%PDF synthetic'):
 return checked(client.post(f'/api/tasks/{tid}/attachments',headers=headers,files={'file':(name,payload)}))['id']

def test_completion_counts_and_history_beyond_old_limit(tmp_path):
 mod,c,h=setup(tmp_path)
 done=make(c,h,'Recently done',status='done')
 toggled=make(c,h,'Toggle')
 checked(c.post(f'/api/tasks/{toggled}/toggle',headers=h))
 completed=checked(c.get(f'/api/tasks/{toggled}'))['completed_at']
 assert completed
 checked(c.put(f'/api/tasks/{toggled}',headers=h,json={'title':'Edited after completion','status':'done'}))
 assert checked(c.get(f'/api/tasks/{toggled}'))['completed_at']==completed
 checked(c.post(f'/api/tasks/{toggled}/toggle',headers=h))
 assert checked(c.get(f'/api/tasks/{toggled}'))['completed_at'] is None
 uid=checked(c.get('/api/me'))['id']
 old=(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()
 with mod.conn() as db:
  db.executemany("INSERT INTO tasks(title,owner_id,status) VALUES(?,?,'done')",[(f'Old task {i}',uid) for i in range(515)])
  db.execute("UPDATE tasks SET completed_at=? WHERE title LIKE 'Old task %'",(old,))
  db.execute("UPDATE tasks SET completed_at=NULL WHERE title='Old task 0'")
 summary=checked(c.get('/api/archive/summary'))
 assert summary=={'period':'30','recent':1,'total':516,'unknown':1}
 assert len(checked(c.get('/api/tasks')))==500
 first=checked(c.get('/api/archive/items?page=1&page_size=40'))
 last=checked(c.get('/api/archive/items?page=13&page_size=40'))
 assert first['total']==516 and len(first['items'])==40 and len(last['items'])==36
 assert checked(c.get('/api/archive/items?period=unknown'))['total']==1
 checked(c.post('/api/archive/preferences',headers=h,json={'period':'90'}))
 assert checked(c.get('/api/archive/summary'))['recent']==515
 assert checked(c.get('/api/archive/items?period=90&kind=agenda'))['total']==515
 assert checked(c.get('/api/archive/items?query=Recently'))['items'][0]['id']==done
 assert c.post('/api/archive/preferences',headers=h,json={'period':'forever'}).status_code==400
 c.close()

def test_ordered_zip_verified_cleanup_and_privacy(tmp_path):
 mod,c,h=setup(tmp_path)
 tid=make(c,h,'=synthetic / activity',status='done',description='Complete text',labels=['TEST'])
 aid=attach(c,h,tid,'same.pdf',b'first content')
 aid2=attach(c,h,tid,'same.pdf',b'second content')
 open_id=make(c,h,'Open item')
 open_aid=attach(c,h,open_id,'open.txt',b'keep me')
 checked(c.post('/api/users',headers=h,json={'username':'colleague','display_name':'Synthetic colleague','password':'synthetic colleague password','role':'user'}))
 other=TestClient(mod.app);oh={'X-NextDo-CSRF':checked(other.get('/api/csrf'))['csrf']}
 checked(other.post('/api/login',headers=oh,json={'username':'colleague','password':'synthetic colleague password'}))
 private_id=make(other,oh,'Private colleague',status='done')
 private_aid=attach(other,oh,private_id,'private.pdf',b'private data')
 assert other.get('/api/archive/storage').status_code==403
 assert other.post('/api/archive/verify-export',headers=oh,files={'file':('test.zip',b'bad')}).status_code==403
 stats=checked(c.get('/api/archive/storage'))
 assert stats['attachment_count']==4
 assert stats['completed_visible']==1
 assert stats['parts']['attachments']==sum(map(len,[b'first content',b'second content',b'keep me',b'private data']))
 assert checked(c.get('/api/archive/preview?label=TEST'))['attachments']==2
 exp=c.get('/api/archive/export?state=all')
 assert exp.status_code==200,exp.text[:200] if exp.status_code!=200 else ''
 raw=exp.content
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.testzip() is None
  manifest=json.loads(z.read('manifest.json'))
  files=manifest['attachments']
  assert {a['id'] for a in files}=={aid,aid2,open_aid}
  assert all(a['path'].endswith('.pdf') for a in files if a['id'] in (aid,aid2))
  assert all('..' not in Path(n).parts for n in z.namelist())
  assert len([n for n in z.namelist() if n.endswith('Scheda_attivita.txt')])==2
  assert all('Private colleague' not in n for n in z.namelist())
  workbook=load_workbook(io.BytesIO(z.read('Indice_archivio.xlsx')),read_only=True)
  assert workbook.sheetnames==['Attività','Allegati','Avanzamenti']
  rows=list(workbook['Attività'].iter_rows())
  formula_cell=next(row[1] for row in rows[1:] if row[0].value==tid)
  assert formula_cell.data_type=='s' and formula_cell.value=='=synthetic / activity'
  workbook.close()
  corrupt=io.BytesIO()
  with zipfile.ZipFile(corrupt,'w') as bad:
   for n in z.namelist():bad.writestr(n,b'wrong' if n==files[0]['path'] else z.read(n))
 assert c.post('/api/archive/verify-export',headers=h,files={'file':('bad.zip',corrupt.getvalue())}).status_code in (400,409)
 assert c.get('/api/attachments/'+str(aid)).content==b'first content'
 verified=checked(c.post('/api/archive/verify-export',headers=h,files={'file':('archive.zip',raw)}))
 assert verified['count']==2 and verified['skipped']==1
 assert c.post('/api/archive/cleanup',headers=h,json={'token':verified['token'],'confirm':'NO'}).status_code==400
 assert c.post('/api/archive/cleanup',json={'token':verified['token'],'confirm':'ELIMINA ALLEGATI'}).status_code==403
 # Reopening after verification invalidates the whole plan; nothing is removed.
 checked(c.post(f'/api/tasks/{tid}/toggle',headers=h))
 assert c.post('/api/archive/cleanup',headers=h,json={'token':verified['token'],'confirm':'ELIMINA ALLEGATI'}).status_code==409
 assert c.get('/api/attachments/'+str(aid)).status_code==200
 checked(c.post(f'/api/tasks/{tid}/toggle',headers=h))
 verified=checked(c.post('/api/archive/verify-export',headers=h,files={'file':('archive.zip',raw)}))
 cleaned=checked(c.post('/api/archive/cleanup',headers=h,json={'token':verified['token'],'confirm':'ELIMINA ALLEGATI'}))
 assert cleaned=={'removed':2,'freed_bytes':len(b'first content')+len(b'second content'),'unlink_failed':0}
 assert checked(c.get(f'/api/tasks/{tid}'))['attachments']==[]
 assert checked(c.get(f'/api/tasks/{tid}'))['status']=='done'
 assert c.get('/api/attachments/'+str(open_aid)).content==b'keep me'
 assert other.get('/api/attachments/'+str(private_aid)).content==b'private data'
 assert c.post('/api/archive/cleanup',headers=h,json={'token':verified['token'],'confirm':'ELIMINA ALLEGATI'}).status_code==409
 assert checked(c.post('/api/archive/vacuum',headers=h,json={'confirm':'OTTIMIZZA'}))['ok']
 other.close();c.close()

def test_legacy_completion_migration_uses_only_progress(tmp_path):
 from app.archive_storage import upgrade
 db_path=tmp_path/'legacy.sqlite3'
 with sqlite3.connect(db_path) as c:
  c.executescript("""
    CREATE TABLE users(id INTEGER PRIMARY KEY);
    CREATE TABLE tasks(id INTEGER PRIMARY KEY,status TEXT);
    CREATE TABLE task_progress(id INTEGER PRIMARY KEY,task_id INTEGER,old_status TEXT,new_status TEXT,created_at TEXT);
    INSERT INTO tasks VALUES(1,'done'),(2,'done'),(3,'todo');
    INSERT INTO task_progress VALUES(1,1,'todo','done','2025-02-03 10:00:00'),(2,1,'done','done','2025-03-01 10:00:00');
  """)
 upgrade(db_path,tmp_path);upgrade(db_path,tmp_path)
 with sqlite3.connect(db_path) as c:
  assert c.execute('SELECT completed_at FROM tasks WHERE id=1').fetchone()[0]=='2025-02-03T10:00:00Z'
  assert c.execute('SELECT completed_at FROM tasks WHERE id=2').fetchone()[0] is None
  c.execute("UPDATE tasks SET status='done' WHERE id=3")
  assert c.execute('SELECT completed_at FROM tasks WHERE id=3').fetchone()[0]
  c.execute("UPDATE tasks SET status='todo' WHERE id=3")
  assert c.execute('SELECT completed_at FROM tasks WHERE id=3').fetchone()[0] is None
 assert len(list(tmp_path.glob('nextdo-before-archive-*.sqlite3')))==1
