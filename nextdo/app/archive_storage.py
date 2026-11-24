"""Visible-task archive, measured storage, and verified attachment evacuation."""
from __future__ import annotations
import hashlib,json,os,re,secrets,shutil,sqlite3,tempfile,time,unicodedata,zipfile
from datetime import datetime,date,timedelta,timezone
from pathlib import Path
from typing import Optional
from fastapi import Request,HTTPException,UploadFile,File
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel,Field
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

PERIODS=('7','30','90','year')
MAX_SOURCE=500*1024**2
MAX_ARCHIVE=550*1024**2
MAX_ENTRIES=20000
MAX_TASKS=10000
MONTHS=('Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre')
def fail(message,status=400):raise HTTPException(status_code=status,detail=message)

def upgrade(db_path,data_path):
 c=sqlite3.connect(db_path,timeout=20)
 try:
  cols={r[1] for r in c.execute('PRAGMA table_info(tasks)')}
  if 'completed_at' not in cols:
   # SQLite-only schema backup; files are not changed by this migration.
   if c.execute('SELECT 1 FROM tasks LIMIT 1').fetchone():
    backup=Path(data_path)/('nextdo-before-archive-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+secrets.token_hex(3)+'.sqlite3')
    dest=sqlite3.connect(backup)
    try:c.backup(dest)
    finally:dest.close()
    os.chmod(backup,0o600)
   with c:
    c.execute('ALTER TABLE tasks ADD COLUMN completed_at TEXT')
    # Only a recorded status transition is evidence. No updated_at/created_at guess.
    c.execute("""UPDATE tasks SET completed_at=(
      SELECT strftime('%Y-%m-%dT%H:%M:%SZ',tp.created_at)
      FROM task_progress tp WHERE tp.task_id=tasks.id AND tp.old_status<>tp.new_status
      ORDER BY tp.id DESC LIMIT 1)
      WHERE status='done' AND (SELECT tp.new_status FROM task_progress tp
      WHERE tp.task_id=tasks.id AND tp.old_status<>tp.new_status ORDER BY tp.id DESC LIMIT 1)='done'""")
  with c:
   c.executescript("""
    CREATE TABLE IF NOT EXISTS archive_preferences(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,period TEXT NOT NULL DEFAULT '30');
    CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(status,completed_at);
    CREATE TRIGGER IF NOT EXISTS nextdo_completed_insert AFTER INSERT ON tasks WHEN NEW.status='done'
      BEGIN UPDATE tasks SET completed_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=NEW.id; END;
    CREATE TRIGGER IF NOT EXISTS nextdo_completed_update AFTER UPDATE OF status ON tasks WHEN OLD.status<>NEW.status
      BEGIN UPDATE tasks SET completed_at=CASE WHEN NEW.status='done' THEN strftime('%Y-%m-%dT%H:%M:%SZ','now') ELSE NULL END WHERE id=NEW.id; END;
   """)
 finally:c.close()

def local_date(raw,tz):
 if not raw:return None
 try:
  dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
  return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(tz).date()
 except (ValueError,OverflowError,AttributeError):return None

def period_start(period,tz):
 today=datetime.now(tz).date()
 return date(today.year,1,1) if period=='year' else today-timedelta(days=int(period)-1)

def scope_filter(c,u,accessible,*,state='done',period='all',month='',kind='all',course_id=None,project_id=None,label='',query='',tz):
 if state not in ('all','open','done') or period not in ('all','unknown',*PERIODS) or kind not in ('all','agenda','task','appointment','note'):fail('Filtro archivio non valido')
 if month:
  try:date.fromisoformat(month+'-01')
  except ValueError:fail('Mese non valido')
  if not re.fullmatch(r'\d{4}-\d{2}',month):fail('Mese non valido')
 if len(label)>60 or len(query)>250:fail('Filtro troppo lungo')
 sql='SELECT t.* FROM tasks t WHERE 1=1';args=[]
 if state!='all':sql+=' AND t.status '+('=' if state=='done' else '<>')+" 'done'"
 if kind=='agenda':sql+=" AND t.kind IN ('task','appointment')"
 elif kind!='all':sql+=' AND t.kind=?';args.append(kind)
 if project_id is not None:sql+=' AND t.project_id=?';args.append(project_id)
 if course_id is not None:
  sql+=' AND EXISTS(SELECT 1 FROM task_courses tc WHERE tc.task_id=t.id AND tc.course_id=?)';args.append(course_id)
 # Archive dates mean actual completion for done tasks; creation for open tasks.
 sql+=" ORDER BY CASE WHEN t.status='done' THEN t.completed_at ELSE t.created_at END DESC,t.id DESC"
 for t in c.execute(sql,args):
  if not accessible(c,u,t):continue
  when=local_date(t['completed_at'] if t['status']=='done' else t['created_at'],tz)
  if period=='unknown' and when:continue
  if period in PERIODS and (not when or not period_start(period,tz)<=when<=datetime.now(tz).date()):continue
  if month and (not when or when.strftime('%Y-%m')!=month):continue
  if label and label not in json.loads(t['labels'] or '[]'):continue
  if query and query.casefold() not in (t['title']+' '+(t['description'] or '')).casefold():continue
  yield t

def safe_file(root,stored):
 if not isinstance(stored,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',stored) or stored in ('.','..'):return None
 p=root/stored
 if p.is_symlink() or not p.is_file():return None
 return p

def digest(stream,limit):
 h=hashlib.sha256();size=0
 while True:
  part=stream.read(1024*1024)
  if not part:break
  size+=len(part)
  if size>limit:fail('Dimensione allegato non coerente')
  h.update(part)
 return size,h.hexdigest()

def clean_name(name,limit=85):
 s=unicodedata.normalize('NFKC',str(name or ''))
 s=re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]','_',s).strip(' .')
 return (s or 'Senza titolo')[:limit].rstrip(' .') or 'Senza titolo'

def excel_row(sheet,values):
 cells=[]
 for v in values:
  if isinstance(v,str):
   v=ILLEGAL_CHARACTERS_RE.sub('',v)[:32767]
   cell=WriteOnlyCell(sheet,value=v);cell.data_type='s';cells.append(cell)
  else:cells.append(v)
 sheet.append(cells)

def storage(data,db,files):
 parts={'database':0,'attachments':0,'backups':0,'personal':0,'other':0}
 for root,dirs,names in os.walk(data,followlinks=False):
  dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink()]
  for name in names:
   p=Path(root)/name
   try:
    if p.is_symlink() or not p.is_file():continue
    rel=p.relative_to(data);first=rel.parts[0]
    if len(rel.parts)==1 and name in (db.name,db.name+'-wal',db.name+'-shm',db.name+'-journal'):key='database'
    elif first==files.name:key='attachments'
    elif first=='personal':key='personal'
    elif first in ('backups','backup') or (len(rel.parts)==1 and name.startswith('nextdo-before-') and name.endswith(('.zip','.sqlite3'))):key='backups'
    else:key='other'
    parts[key]+=p.stat().st_size
   except (FileNotFoundError,PermissionError,OSError):continue
 disk=shutil.disk_usage(data)
 return {'parts':parts,'total':sum(parts.values()),'disk_total':disk.total,'disk_free':disk.free,'disk_used':disk.used}

class Preferences(BaseModel):
 period:str
class Cleanup(BaseModel):
 token:str=Field(min_length=10,max_length=150)
 confirm:str=Field(max_length=80)
class Vacuum(BaseModel):
 confirm:str=Field(max_length=80)

def register(app,*,conn,user,csrf,accessible,can_edit,taskdetail,record,data,db,files,db_lock,tz):
 # Ephemeral per-admin verified plans. No data or permissions transferred across users.
 plans={}
 def admin(req,write=False):
  u=user(req)
  if u['role']!='admin':fail('Accesso riservato agli amministratori',403)
  if write:csrf(req)
  return u
 def pref(c,u):
  row=c.execute('SELECT period FROM archive_preferences WHERE user_id=?',(u['id'],)).fetchone()
  return row[0] if row and row[0] in PERIODS else '30'
 def candidates(c,u,**kwargs):
  return scope_filter(c,u,accessible,tz=tz,**kwargs)
 def attachments(c,t):
  return list(c.execute('SELECT * FROM attachments WHERE task_id=? ORDER BY id',(t['id'],)))
 @app.get('/api/archive/summary')
 def summary(req:Request):
  u=user(req)
  with conn() as c:
   period=pref(c,u);start=period_start(period,tz);today=datetime.now(tz).date()
   total=recent=unknown=0
   for t in candidates(c,u,state='done',kind='agenda'):
    total+=1;d=local_date(t['completed_at'],tz)
    if not d:unknown+=1
    elif start<=d<=today:recent+=1
   return {'period':period,'recent':recent,'total':total,'unknown':unknown}
 @app.post('/api/archive/preferences')
 def preferences(b:Preferences,req:Request):
  u=user(req);csrf(req)
  if b.period not in PERIODS:fail('Periodo non valido')
  with conn() as c:c.execute('INSERT INTO archive_preferences(user_id,period) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET period=excluded.period',(u['id'],b.period))
  return {'ok':True,'period':b.period}
 @app.get('/api/archive/items')
 def items(req:Request,state:str='done',period:str='all',month:str='',kind:str='all',course_id:Optional[int]=None,project_id:Optional[int]=None,label:str='',query:str='',page:int=1,page_size:int=40):
  u=user(req)
  if page<1 or page_size<1 or page_size>100:fail('Paginazione non valida')
  with conn() as c:
   result=[];total=0
   for t in candidates(c,u,state=state,period=period,month=month,kind=kind,course_id=course_id,project_id=project_id,label=label,query=query):
    if (page-1)*page_size<=total<page*page_size:result.append(taskdetail(c,t,u))
    total+=1
   return {'items':result,'total':total,'page':page,'page_size':page_size}
 @app.get('/api/archive/storage')
 def usage(req:Request):
  u=admin(req)
  with conn() as c:
   stats=storage(data,db,files)
   stats['completed_visible']=sum(1 for _ in candidates(c,u,state='done'))
   stats['completed_unknown']=sum(1 for _ in candidates(c,u,state='done',period='unknown'))
   stats['attachment_count']=c.execute('SELECT COUNT(*) FROM attachments').fetchone()[0]
   stats['db_reclaimable_estimate']=c.execute('PRAGMA freelist_count').fetchone()[0]*c.execute('PRAGMA page_size').fetchone()[0]
  return stats
 @app.get('/api/archive/preview')
 def preview(req:Request,state:str='done',period:str='all',month:str='',kind:str='all',course_id:Optional[int]=None,project_id:Optional[int]=None,label:str='',query:str=''):
  u=user(req)
  with conn() as c:
   total=count=size=missing=cleanup=0;sample=[]
   for t in candidates(c,u,state=state,period=period,month=month,kind=kind,course_id=course_id,project_id=project_id,label=label,query=query):
    total+=1
    rows=attachments(c,t)
    for a in rows:
     p=safe_file(files,a['stored']);count+=1
     if not p:missing+=1;continue
     size+=p.stat().st_size
     if t['status']=='done' and can_edit(c,u,t):cleanup+=1
    if len(sample)<20:sample.append({'id':t['id'],'title':t['title'],'status':t['status'],'completed_at':t['completed_at'],'attachments':len(rows)})
   return {'tasks':total,'attachments':count,'bytes':size,'missing':missing,'eligible_cleanup':cleanup,'sample':sample,'limit_bytes':MAX_SOURCE}
 @app.get('/api/archive/export')
 def export(req:Request,state:str='done',period:str='all',month:str='',kind:str='all',course_id:Optional[int]=None,project_id:Optional[int]=None,label:str='',query:str=''):
  u=user(req)
  temp=None
  try:
   with conn() as c:
    tasks=list(candidates(c,u,state=state,period=period,month=month,kind=kind,course_id=course_id,project_id=project_id,label=label,query=query))
    if not tasks:fail('Nessuna attività corrisponde ai filtri')
    if len(tasks)>MAX_TASKS:fail('Selezione troppo ampia: restringere i filtri',413)
    selected=[];size=0;count=0
    for t in tasks:
     rows=[]
     size+=len((t['title']+(t['description'] or '')).encode('utf-8'))*2+2048
     for a in attachments(c,t):
      p=safe_file(files,a['stored'])
      if not p:fail('Un allegato è mancante: correggere il problema prima di esportare',409)
      n=p.stat().st_size;size+=n;count+=1;rows.append((a,p,n))
     selected.append((t,rows))
    if size>MAX_SOURCE or len(tasks)+count+2>MAX_ENTRIES:fail('Selezione troppo ampia: esportare per intervalli o progetti (massimo 500 MiB per ZIP)',413)
    if shutil.disk_usage(data).free<size+20*1024**2:fail('Spazio temporaneo insufficiente: restringere i filtri',507)
    temp=Path(tempfile.mkdtemp(prefix='.archive-export-',dir=data));target=temp/'NextDo_Archivio.zip'
    book=Workbook(write_only=True);ts=book.create_sheet('Attività');fs=book.create_sheet('Allegati')
    ts.freeze_panes='A2';fs.freeze_panes='A2'
    excel_row(ts,['ID','Titolo','Tipo','Stato','Data completamento UTC','Creato UTC','Scadenza','Progetto','CdS','Etichette','Descrizione (testo completo nella scheda)','Cartella','Allegati'])
    excel_row(fs,['ID allegato','ID attività','Nome originale','Dimensione byte','SHA-256','Percorso ZIP'])
    manifest={'format':'nextdo-archive-v1','attachments':[]}
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as z:
     for t,rows in selected:
      when=local_date(t['completed_at'] if t['status']=='done' else t['created_at'],tz)
      prefix=(str(when.year)+'/'+str(when.month).zfill(2)+'_'+MONTHS[when.month-1] if when else 'Data_non_disponibile')
      folder=prefix+'/'+str(t['id'])+'_'+clean_name(t['title'])
      project=c.execute('SELECT title FROM projects WHERE id=?',(t['project_id'],)).fetchone() if t['project_id'] else None
      courses=', '.join(x[0] for x in c.execute('SELECT c.code FROM task_courses tc JOIN courses c ON c.id=tc.course_id WHERE tc.task_id=? ORDER BY c.code',(t['id'],)))
      labels=', '.join(json.loads(t['labels'] or '[]'))
      info=[('ID',str(t['id'])),('Titolo',t['title']),('Tipo',t['kind']),('Stato',t['status']),('Completamento UTC',t['completed_at'] or 'Non disponibile'),('Creazione UTC',t['created_at'] or ''),('Scadenza',t['due_at'] or ''),('Progetto',project[0] if project else ''),('CdS',courses),('Etichette',labels)]
      z.writestr(folder+'/Scheda_attivita.txt','\n'.join(k+': '+str(v) for k,v in info)+'\n\nDescrizione:\n'+(t['description'] or ''))
      excel_row(ts,[t['id'],t['title'],t['kind'],t['status'],t['completed_at'] or '',t['created_at'],t['due_at'] or '',project[0] if project else '',courses,labels,t['description'] or '',folder,len(rows)])
      for a,p,n in rows:
       # Numeric prefix prevents collisions; preserve original extension after truncation.
       leaf=clean_name(Path(a['filename']).stem,70)+clean_name(Path(a['filename']).suffix,15) if Path(a['filename']).suffix else clean_name(a['filename'])
       member=folder+'/Allegati/'+str(a['id'])+'_'+leaf
       hh=hashlib.sha256();actual=0
       with p.open('rb') as inp,z.open(member,'w') as out:
        while True:
         block=inp.read(1024*1024)
         if not block:break
         actual+=len(block)
         if actual>n:fail('Allegato modificato durante l’esportazione',409)
         hh.update(block);out.write(block)
       if actual!=n:fail('Allegato modificato durante l’esportazione',409)
       entry={'id':a['id'],'task_id':t['id'],'path':member,'size':actual,'sha256':hh.hexdigest()}
       manifest['attachments'].append(entry)
       excel_row(fs,[a['id'],t['id'],a['filename'],actual,entry['sha256'],member])
     index=temp/'Indice_archivio.xlsx';book.save(index);z.write(index,'Indice_archivio.xlsx')
     z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
    os.chmod(target,0o600)
   return FileResponse(target,media_type='application/zip',filename='NextDo_Archivio_'+datetime.now(tz).strftime('%Y%m%d_%H%M')+'.zip',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'},background=BackgroundTask(shutil.rmtree,temp,ignore_errors=True))
  except Exception:
   if temp:shutil.rmtree(temp,ignore_errors=True)
   raise
 @app.post('/api/archive/verify-export')
 def verify(req:Request,file:UploadFile=File(...)):
  u=admin(req,True)
  with db_lock:plans.pop(u['id'],None)
  # The actual saved ZIP must be re-selected. Never extract untrusted paths to disk.
  if file.size is None or file.size>MAX_ARCHIVE:fail('ZIP oltre il limite di 550 MiB',413)
  try:
   with zipfile.ZipFile(file.file) as z:
    infos=z.infolist()
    if len(infos)>MAX_ENTRIES or len({x.filename for x in infos})!=len(infos):fail('ZIP con voci duplicate o troppo numerose')
    meta=z.getinfo('manifest.json')
    if meta.file_size>16*1024**2:fail('Manifesto troppo grande')
    manifest=json.loads(z.read(meta))
    entries=manifest.get('attachments')
    if manifest.get('format')!='nextdo-archive-v1' or not isinstance(entries,list) or len(entries)>MAX_ENTRIES:fail('Archivio NextDo non valido')
    ids=set();selected=[];skipped=0;size=0
    with conn() as c:
     for e in entries:
      if not isinstance(e,dict) or type(e.get('id')) is not int or e['id'] in ids or type(e.get('task_id')) is not int or type(e.get('size')) is not int or not 0<=e['size']<=15*1024**2 or not isinstance(e.get('path'),str) or not isinstance(e.get('sha256'),str):fail('Manifesto allegati non valido')
      ids.add(e['id'])
      a=c.execute('SELECT * FROM attachments WHERE id=?',(e['id'],)).fetchone()
      if not a or a['task_id']!=e['task_id']:skipped+=1;continue
      t=c.execute('SELECT * FROM tasks WHERE id=?',(a['task_id'],)).fetchone()
      if not t or t['status']!='done' or not accessible(c,u,t) or not can_edit(c,u,t):skipped+=1;continue
      p=safe_file(files,a['stored'])
      if not p:fail('Un allegato selezionato non è presente sul server',409)
      n=p.stat().st_size;member=z.getinfo(e['path'])
      if member.is_dir() or member.file_size!=n or n!=e['size'] or n>15*1024**2 or size+n>MAX_SOURCE:fail('Dimensione allegato non corrispondente')
      with z.open(member) as inp:exported=digest(inp,n)
      with p.open('rb') as inp:current=digest(inp,n)
      if current!=exported or current!=(n,e['sha256']):fail('Lo ZIP non contiene una copia identica di tutti gli allegati selezionati',409)
      selected.append({'id':a['id'],'task_id':t['id'],'stored':a['stored'],'filename':a['filename'],'title':t['title'],'size':n,'sha256':current[1]});size+=n
     token=secrets.token_urlsafe(32)
     if selected:plans[u['id']]={'token':token,'until':time.monotonic()+1200,'items':selected}
     else:plans.pop(u['id'],None)
   return {'token':token if selected else None,'count':len(selected),'bytes':size,'skipped':skipped,'sample':[{k:x[k] for k in ('id','task_id','filename','title','size')} for x in selected[:100]],'expires_minutes':20}
  except (zipfile.BadZipFile,KeyError,ValueError,TypeError,AttributeError,RuntimeError,EOFError,NotImplementedError,OSError):fail('ZIP non valido o danneggiato')
 @app.post('/api/archive/cleanup')
 def cleanup(b:Cleanup,req:Request):
  u=admin(req,True)
  if b.confirm!='ELIMINA ALLEGATI':fail('Digitare ELIMINA ALLEGATI')
  with db_lock:
   plan=plans.get(u['id'])
   if not plan or plan['until']<time.monotonic() or not secrets.compare_digest(plan['token'],b.token):fail('Verifica scaduta: selezionare nuovamente lo ZIP',409)
   paths=[]
   with conn() as c:
    for e in plan['items']:
     a=c.execute('SELECT * FROM attachments WHERE id=?',(e['id'],)).fetchone()
     t=c.execute('SELECT * FROM tasks WHERE id=?',(e['task_id'],)).fetchone()
     if not a or a['task_id']!=e['task_id'] or a['stored']!=e['stored'] or a['filename']!=e['filename'] or not t or t['status']!='done' or not accessible(c,u,t) or not can_edit(c,u,t):fail('Archivio modificato: verificare nuovamente lo ZIP',409)
     p=safe_file(files,a['stored'])
     if not p:fail('Allegato non più disponibile',409)
     with p.open('rb') as inp:current=digest(inp,e['size'])
     if current!=(e['size'],e['sha256']):fail('Allegato modificato: verificare nuovamente lo ZIP',409)
     if c.execute('SELECT COUNT(*) FROM attachments WHERE stored=?',(a['stored'],)).fetchone()[0]!=1:fail('Riferimento allegato duplicato: pulizia annullata',409)
     paths.append((p,e))
    for _,e in paths:
     c.execute('DELETE FROM attachments WHERE id=?',(e['id'],));record(c,u['id'],'archive_verified_attachment_delete','task',e['task_id'])
   # Database references are committed first; a failed unlink leaves a file, never a broken reference.
   plans.pop(u['id'],None);freed=0;failed=0
   for p,e in paths:
    try:p.unlink();freed+=e['size']
    except OSError:failed+=1
   return {'removed':len(paths),'freed_bytes':freed,'unlink_failed':failed}
 @app.post('/api/archive/vacuum')
 def vacuum(b:Vacuum,req:Request):
  u=admin(req,True)
  if b.confirm!='OTTIMIZZA':fail('Digitare OTTIMIZZA')
  with db_lock:
   before=sum(p.stat().st_size for p in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm')) if p.exists())
   if shutil.disk_usage(data).free<2*db.stat().st_size+10*1024**2:fail('Spazio insufficiente per ottimizzare in sicurezza',507)
   c=sqlite3.connect(db,timeout=20)
   try:
    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':fail('Verifica integrità non superata: nessuna ottimizzazione eseguita',409)
    c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    c.execute('VACUUM');c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':fail('Verifica integrità finale non superata',500)
   finally:c.close()
   with conn() as c:record(c,u['id'],'archive_vacuum','database',None)
   after=sum(p.stat().st_size for p in (db,Path(str(db)+'-wal'),Path(str(db)+'-shm')) if p.exists())
  return {'ok':True,'before':before,'after':after,'freed_bytes':max(0,before-after)}
