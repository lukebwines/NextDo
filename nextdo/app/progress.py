"""Per-task progress entries used by the colleague dashboard and project cards."""
from datetime import datetime,timezone
from fastapi import Request
from pydantic import BaseModel,Field
from .workspace import can_read,can_move,can_finish,fail

class ProgressUpdate(BaseModel):
 status:str
 note:str=Field(default='',max_length=1500)

def register_routes(app,conn,user,csrf,record):
 @app.post('/api/tasks/{tid}/progress')
 def update(tid:int,b:ProgressUpdate,req:Request):
  u=user(req);csrf(req)
  if b.status not in ('todo','doing','waiting','done'):fail('Stato non valido',400)
  note=b.note.strip()
  with conn() as c:
   t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
   if not t:fail('Attività non trovata',404)
   allowed=can_finish(c,u,t) if b.status=='done' else can_move(c,u,t)
   if not allowed:fail('Non puoi aggiornare questa attività')
   if t['completion_mode']=='per_course' and c.execute('SELECT 1 FROM task_courses WHERE task_id=?',(tid,)).fetchone():
    if (b.status=='done')!=(t['status']=='done'):
     fail('Completa o riapri la scadenza attraverso i singoli CdS',400)
   if t['status']==b.status and not note:fail('Indicare una modifica di stato o una breve nota',400)
   c.execute('UPDATE tasks SET status=?,updated_at=? WHERE id=?',(b.status,datetime.now(timezone.utc).isoformat(),tid))
   r=c.execute('INSERT INTO task_progress(task_id,actor_id,old_status,new_status,note) VALUES(?,?,?,?,?)',(tid,u['id'],t['status'],b.status,note))
   record(c,u['id'],'progress','task',tid)
  return {'ok':True,'id':r.lastrowid}
 @app.get('/api/tasks/{tid}/progress')
 def history(tid:int,req:Request):
  u=user(req)
  with conn() as c:
   t=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
   if not t:fail('Attività non trovata',404)
   if not can_read(c,u,t):fail('Non puoi consultare questa attività')
   return [dict(r) for r in c.execute("""
    SELECT tp.id,tp.old_status,tp.new_status,tp.note,tp.created_at,u.display_name AS actor
    FROM task_progress tp JOIN users u ON u.id=tp.actor_id
    WHERE tp.task_id=? ORDER BY tp.id DESC LIMIT 100""",(tid,))]
