"""Personal agenda isolated from professional task APIs."""
from datetime import date,datetime,timedelta
from calendar import monthrange
from zoneinfo import ZoneInfo
import os
TZ=ZoneInfo(os.environ.get('NEXTDO_TZ','Europe/Rome'))
from fastapi import HTTPException,Request

def fail(msg,code=400):raise HTTPException(code,msg)

def ensure(c):
 from . import private_indicator
 private_indicator.ensure(c)
 c.execute("""CREATE TABLE IF NOT EXISTS private_items(
 id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL,
 due_at TEXT,status TEXT NOT NULL DEFAULT 'todo',priority TEXT NOT NULL DEFAULT 'normal',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
 cols={r[1] for r in c.execute("PRAGMA table_info(private_items)")}
 if "recurrence" not in cols:c.execute("ALTER TABLE private_items ADD COLUMN recurrence TEXT NOT NULL DEFAULT 'none'")
 if "recurrence_anchor" not in cols:c.execute("ALTER TABLE private_items ADD COLUMN recurrence_anchor TEXT")
 if "snoozed_until" not in cols:c.execute("ALTER TABLE private_items ADD COLUMN snoozed_until TEXT")
 c.execute("CREATE INDEX IF NOT EXISTS private_items_owner ON private_items(owner_id,status,due_at)")

def owner_id(c,identity):
 r=c.execute("SELECT u.id FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE p.owner=? AND u.active=1",(identity,)).fetchone()
 if not r:fail("Account non disponibile",401)
 return r[0]

def list_items(c,uid):
 return [dict(r) for r in c.execute("SELECT id,title,description,kind,due_at,status,priority,recurrence,snoozed_until FROM private_items WHERE owner_id=? ORDER BY status='done',due_at IS NULL,due_at,id DESC",(uid,))]

def checked(b,allow_undated_done=False):
 title=b.get("title");description=b.get("description","");kind=b.get("kind","task")
 due=b.get("due_at") or None;status=b.get("status","todo");priority=b.get("priority","normal")
 if not isinstance(title,str) or not title.strip() or len(title)>250 or not isinstance(description,str) or len(description)>20000:fail("Titolo o descrizione non validi")
 if kind not in ("task","deadline","appointment") or status not in ("review","todo","done") or priority not in ("low","normal","high","urgent"):fail("Valori non validi")
 if due is not None:
  if not isinstance(due,str) or len(due)>25:fail("Data non valida")
  try:
   if len(due)==10:date.fromisoformat(due)
   else:
    d=datetime.fromisoformat(due)
    if "T" not in due or d.tzinfo is not None:raise ValueError()
  except ValueError:fail("Data non valida")
 if kind in ("appointment","deadline") and not due and status!="review" and not (status=="done" and allow_undated_done):fail("Inserire una data")
 recurrence=b.get("recurrence","none")
 if recurrence not in ("none","daily","weekly","monthly","yearly"):fail("Ripetizione non valida")
 if recurrence!="none" and (kind!="task" or not due):fail("La ripetizione richiede un'attività con data")
 return title.strip(),description,kind,due,status,priority,recurrence

def next_due(due,anchor,recurrence,now=None):
 original=datetime.fromisoformat(due)
 initial=datetime.fromisoformat(anchor or due)
 now=now or datetime.now(TZ).replace(tzinfo=None)
 if len(due)==10:now=datetime.combine(now.date(),datetime.min.time())
 def advance(d):
  if recurrence=="daily":return d+timedelta(days=1)
  if recurrence=="weekly":return d+timedelta(days=7)
  months=1 if recurrence=="monthly" else 12
  i=d.year*12+d.month-1+months;y,m=divmod(i,12);m+=1
  return d.replace(year=y,month=m,day=min(initial.day,monthrange(y,m)[1]))
 try:
  d=advance(original)
  if recurrence in ("daily","weekly") and d<=now:
   step=timedelta(days=1 if recurrence=="daily" else 7)
   d+=step*((now-d)//step+1)
  while d<=now:d=advance(d)
 except (ValueError,OverflowError):fail("Data successiva non valida")
 return d.date().isoformat() if len(due)==10 else d.isoformat(timespec="seconds")

def create(c,uid,b):
 vals=checked(b)
 return c.execute("INSERT INTO private_items(owner_id,title,description,kind,due_at,status,priority,recurrence,recurrence_anchor) VALUES(?,?,?,?,?,?,?,?,?)",(uid,*vals,vals[3] if vals[6]!="none" else None)).lastrowid

def update(c,uid,i,b):
 old=c.execute("SELECT * FROM private_items WHERE owner_id=? AND id=?",(uid,i)).fetchone()
 if not old:fail("Elemento non trovato",404)
 merged={**dict(old),**b}
 if merged["kind"]!="task" or not merged.get("due_at"):
  if "recurrence" not in b:merged["recurrence"]="none"
 vals=list(checked(merged,allow_undated_done=old['status'] in ('review','done') and old['due_at'] is None))
 anchor=old["recurrence_anchor"] if vals[6]==old["recurrence"] and vals[3]==old["due_at"] else vals[3]
 if vals[6]=="none":anchor=None
 snooze=old["snoozed_until"] if vals[3]==old["due_at"] and vals[4]!="done" else None
 if vals[4]=="done" and old["status"]!="done" and vals[6]!="none":
  if "expected_due" not in b or b["expected_due"]!=old["due_at"]:fail("Ricaricare l'attività ricorrente prima di completarla",409)
  vals[3]=next_due(vals[3],anchor,vals[6]);vals[4]="todo";snooze=None
 c.execute("UPDATE private_items SET title=?,description=?,kind=?,due_at=?,status=?,priority=?,recurrence=?,recurrence_anchor=?,snoozed_until=?,updated_at=CURRENT_TIMESTAMP WHERE owner_id=? AND id=?",(*vals,anchor,snooze,uid,i))
 return {"id":i}

def snooze(c,uid,i,minutes):
 if type(minutes)!=int or minutes not in (0,10,30,60,1440):fail("Rinvio non valido")
 old=c.execute("SELECT kind,status FROM private_items WHERE owner_id=? AND id=?",(uid,i)).fetchone()
 if not old:fail("Elemento non trovato",404)
 if old["kind"]!="task" or old["status"]=="done":fail("Rinvio disponibile per attività aperte")
 until=(datetime.now(TZ)+timedelta(minutes=minutes)).replace(tzinfo=None).isoformat(timespec="seconds") if minutes else None
 c.execute("UPDATE private_items SET snoozed_until=? WHERE owner_id=? AND id=?",(until,uid,i))
 return {"id":i,"snoozed_until":until}

def remove(c,uid,i):
 if not c.execute("DELETE FROM private_items WHERE owner_id=? AND id=?",(uid,i)).rowcount:fail("Elemento non trovato",404)
 return {"ok":True}

def register(app,conn,web_owner,mobile_owner,data_path):
 from . import private_indicator
 private_indicator.register(app,conn,web_owner)
 from . import private_transfer as transfer
 def attach(prefix,authorize):
  @app.get(prefix+"/items")
  def read(req:Request):
   identity=authorize(req,False)
   with conn() as c:return {"items":list_items(c,owner_id(c,identity))}
  @app.post(prefix+"/items")
  def add(req:Request,b:dict):
   identity=authorize(req,True)
   with conn() as c:return {"id":create(c,owner_id(c,identity),b)}
  @app.post(prefix+"/items/{item_id}")
  def edit(item_id:int,req:Request,b:dict):
   identity=authorize(req,True)
   with conn() as c:return update(c,owner_id(c,identity),item_id,b)
  @app.post(prefix+"/items/{item_id}/snooze")
  def postpone(item_id:int,req:Request,b:dict):
   identity=authorize(req,True)
   with conn() as c:return snooze(c,owner_id(c,identity),item_id,b.get("minutes"))
  @app.post(prefix+"/items/{item_id}/delete")
  @app.delete(prefix+"/items/{item_id}")
  def delete(item_id:int,req:Request):
   identity=authorize(req,True)
   with conn() as c:return remove(c,owner_id(c,identity),item_id)
  if prefix!="/api/personal":return
  @app.get(prefix+"/transfers")
  def preview(req:Request):
   identity=authorize(req,False)
   with conn() as c:return transfer.candidates(c,owner_id(c,identity),identity,data_path)
  @app.post(prefix+"/transfers")
  def move(req:Request,b:dict):
   identity=authorize(req,True)
   if b.get("confirm") is not True:fail("Confermare lo spostamento")
   with conn() as c:
    uid=owner_id(c,identity)
    action=b.get("action")
    if action=="mail" and isinstance(b.get("digest"),str):return transfer.move_mail(c,uid,identity,data_path,b["digest"])
    if type(b.get("id")) is int:
     if action=="to_private":return transfer.work_to_private(c,uid,b["id"])
     if action=="to_work":return transfer.to_work(c,uid,b["id"])
    fail("Spostamento non valido")
 attach("/api/personal",web_owner)
 attach("/api/mobile/v1",mobile_owner)
