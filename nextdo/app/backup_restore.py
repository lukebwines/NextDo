"""Restore NextDo ZIP backups; does not accept Home Assistant .tar backups."""
import io,os,re,secrets,shutil,sqlite3,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path
from fastapi import UploadFile,File,Form,Request,HTTPException

MAX_ARCHIVE=40*1024*1024
MAX_UNPACKED=250*1024*1024

def reject(message,status=400):
 raise HTTPException(status_code=status,detail=message)

def db_copy(source,target):
 a=sqlite3.connect(source);b=sqlite3.connect(target)
 try:a.backup(b)
 finally:b.close();a.close()

def unpack(data,folder):
 db=folder/'database.sqlite3';attachments=folder/'attachments';attachments.mkdir()
 names=set();size=0
 try:
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   entries=z.infolist()
   if not entries or len(entries)>800 or len({x.filename for x in entries})!=len(entries):reject('File ZIP con voci mancanti o duplicate')
   for item in entries:
    if item.is_dir():
     if item.filename!='attachments/':reject('Cartella inattesa nel backup')
     continue
    name=item.filename
    if name!='database.sqlite3':
     if not name.startswith('attachments/'):reject('Il backup contiene file inattesi')
     leaf=name[len('attachments/'):]
     if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}',leaf) or leaf in ('.','..'):reject('Allegato non valido')
     names.add(leaf)
    else:leaf=None
    mode=(item.external_attr>>16)&0o170000
    if mode not in (0,0o100000):reject('File non regolare nel backup')
    size+=item.file_size
    if size>MAX_UNPACKED:reject('Backup troppo grande')
    path=db if leaf is None else attachments/leaf
    with z.open(item) as inp,path.open('xb') as out:shutil.copyfileobj(inp,out,1024*1024)
 except (zipfile.BadZipFile,OSError,RuntimeError,EOFError):reject('Backup ZIP danneggiato o non valido')
 if not db.is_file():reject('Database NextDo mancante')
 try:
  source=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
  try:
   source.execute('PRAGMA trusted_schema=OFF')
   if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':reject('Integrità database non valida')
   needed={'users','sessions','groups','memberships','courses','tasks','task_courses','attachments','reminders','notifications','audit','display_keys'}
   found={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   if not needed<=found:reject('Versione database NextDo non compatibile')
   cols=lambda tab:{r[1] for r in source.execute('PRAGMA table_info('+tab+')')}
   if not {'id','username','password','display_name','role','active'}<=cols('users'):reject('Schema account non compatibile')
   if not {'id','title','kind','display_enabled','labels'}<=cols('tasks'):reject('Schema scadenze non compatibile')
   if not {'stored','filename','task_id'}<=cols('attachments'):reject('Schema allegati non compatibile')
   if not source.execute("SELECT 1 FROM users WHERE role='admin' AND active=1 LIMIT 1").fetchone():reject('Manca un amministratore attivo')
   if source.execute('PRAGMA foreign_key_check').fetchone():reject('Riferimenti database non validi')
   if not {r[0] for r in source.execute('SELECT stored FROM attachments')}<=names:reject('Allegati mancanti nell’archivio')
  finally:source.close()
 except sqlite3.DatabaseError:reject('Database SQLite non valido')
 return db,attachments

def register_restore_routes(app,*,user,csrf,db_path,attachments_path,data_path,db_lock):
 @app.post('/api/backup/import')
 async def restore(req:Request,file:UploadFile=File(...),confirm:str=Form(...)):
  actor=user(req)
  if actor['role']!='admin':reject('Accesso riservato agli amministratori',403)
  csrf(req)
  if confirm!='RIPRISTINA':reject('Digitare RIPRISTINA per confermare')
  if not (file.filename or '').lower().endswith('.zip'):reject('Selezionare un archivio ZIP esportato da NextDo')
  raw=await file.read(MAX_ARCHIVE+1)
  if len(raw)>MAX_ARCHIVE:reject('Backup oltre il limite di 40 MB')
  with tempfile.TemporaryDirectory(dir=data_path,prefix='.nextdo-import-') as tmp:
   stage=Path(tmp);new_db,new_files=unpack(raw,stage)
   old_db=stage/'before.sqlite3';old_files=stage/'before-attachments'
   saved=data_path/('nextdo-before-import-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4)+'.zip')
   with db_lock:
    db_copy(db_path,old_db)
    with zipfile.ZipFile(saved,'x',zipfile.ZIP_DEFLATED) as z:
     z.write(old_db,'database.sqlite3')
     for p in attachments_path.iterdir():
      if p.is_file():z.write(p,'attachments/'+p.name)
    os.chmod(saved,0o600)
    moved=False
    try:
     attachments_path.rename(old_files);moved=True
     shutil.copytree(new_files,attachments_path)
     db_copy(new_db,db_path)
     # Imported archives from older NextDo versions must be upgraded before use.
     from . import workspace
     workspace.upgrade(db_path,data_path)
     with sqlite3.connect(db_path) as conn:conn.execute('DELETE FROM sessions')
    except Exception:
     db_copy(old_db,db_path)
     if moved:
      if attachments_path.exists():shutil.rmtree(attachments_path)
      old_files.rename(attachments_path)
     raise
  return {'ok':True,'message':'Ripristino completato. Accedere nuovamente con le credenziali del backup.','pre_restore_backup':saved.name}
