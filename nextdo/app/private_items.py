"""Personal agenda isolated from professional task APIs."""
from datetime import date,datetime
from fastapi import HTTPException,Request

def fail(msg,code=400):raise HTTPException(code,msg)

def ensure(c):
 c.execute("""CREATE TABLE IF NOT EXISTS private_items(
 id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',kind TEXT NOT NULL,
 due_at TEXT,status TEXT NOT NULL DEFAULT 'todo',priority TEXT NOT NULL DEFAULT 'normal',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
 c.execute("CREATE INDEX IF NOT EXISTS private_items_owner ON private_items(owner_id,status,due_at)")

def owner_id(c,identity):
 r=c.execute("SELECT u.id FROM personal_identities p JOIN users u ON u.id=p.user_id WHERE p.owner=? AND u.active=1",(identity,)).fetchone()
 if not r:fail("Account non disponibile",401)
 return r[0]

def list_items(c,uid):
 return [dict(r) for r in c.execute("SELECT id,title,description,kind,due_at,status,priority FROM private_items WHERE owner_id=? ORDER BY status='done',due_at IS NULL,due_at,id DESC",(uid,))]

def checked(b):
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
 if kind in ("appointment","deadline") and not due and status!="review":fail("Inserire una data")
 return title.strip(),description,kind,due,status,priority

def create(c,uid,b):
 vals=checked(b)
 return c.execute("INSERT INTO private_items(owner_id,title,description,kind,due_at,status,priority) VALUES(?,?,?,?,?,?,?)",(uid,*vals)).lastrowid

def update(c,uid,i,b):
 old=c.execute("SELECT * FROM private_items WHERE owner_id=? AND id=?",(uid,i)).fetchone()
 if not old:fail("Elemento non trovato",404)
 vals=checked({**dict(old),**b})
 c.execute("UPDATE private_items SET title=?,description=?,kind=?,due_at=?,status=?,priority=?,updated_at=CURRENT_TIMESTAMP WHERE owner_id=? AND id=?",(*vals,uid,i))
 return {"id":i}

def remove(c,uid,i):
 if not c.execute("DELETE FROM private_items WHERE owner_id=? AND id=?",(uid,i)).rowcount:fail("Elemento non trovato",404)
 return {"ok":True}

def register(app,conn,web_owner,mobile_owner):
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
  @app.delete(prefix+"/items/{item_id}")
  def delete(item_id:int,req:Request):
   identity=authorize(req,True)
   with conn() as c:return remove(c,owner_id(c,identity),item_id)
 attach("/api/personal",web_owner)
 attach("/api/mobile/v1",mobile_owner)
