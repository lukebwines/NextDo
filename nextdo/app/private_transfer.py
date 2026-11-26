"""Explicit, transactional moves. Never silently discard professional metadata."""
import hashlib,json
from . import private_items,cloudflare_mail

def fail(s,code=409):private_items.fail(s,code)

def table(c,name):
 return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())

def eligible(c,t,mail=False):
 if t["scope"]!="personal" or t["project_id"] or t["group_id"] or t["assigned_to"] or t["display_enabled"] or t["completion_mode"]!="global" or t["recurrence"]!="none":return "Attività condivisa, ricorrente o collegata a un progetto"
 if t["kind"] not in ("task","appointment") or t["status"] not in ("todo","review","done"):return "Tipo o stato non trasferibile"
 if t["start_at"] or dict(t).get("address"):return "Data iniziale o indirizzo da conservare"
 if json.loads(t["labels"] or "[]") not in ([],["Cloudflare Mail","Da verificare"]):return "Etichette professionali presenti"
 for tab in ("task_courses","attachments","reminders","task_progress","external_course_progress","imported_calendar","gmail_auto_tasks"):
  if table(c,tab) and c.execute("SELECT 1 FROM "+tab+" WHERE task_id=? LIMIT 1",(t["id"],)).fetchone():return "Collegamenti o storico da conservare ("+tab+")"
 if not mail and c.execute("SELECT 1 FROM cloudflare_mail_tasks WHERE task_id=?",(t["id"],)).fetchone():return "Usare la riclassificazione email"
 try:private_items.checked(payload(t))
 except Exception:return "Dati non compatibili con l'agenda personale"
 return None

def payload(t):
 return {"title":t["title"],"description":t["description"] or "","kind":"appointment" if t["kind"]=="appointment" else ("deadline" if t["due_at"] else "task"),"due_at":t["due_at"],"status":t["status"],"priority":"urgent" if t["priority"]=="critical" else t["priority"]}

def work_to_private(c,uid,tid):
 t=c.execute("SELECT * FROM tasks WHERE id=? AND owner_id=?",(tid,uid)).fetchone()
 if not t:fail("Attività non trovata",404)
 reason=eligible(c,t)
 if reason:fail(reason)
 i=private_items.create(c,uid,payload(t))
 c.execute("DELETE FROM tasks WHERE id=?",(tid,))
 c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",(uid,"move_to_private","task",tid))
 return {"id":i}

def to_work(c,uid,i):
 t=c.execute("SELECT * FROM private_items WHERE id=? AND owner_id=?",(i,uid)).fetchone()
 if not t:fail("Impegno non trovato",404)
 if t["recurrence"]!="none" or t["snoozed_until"]:fail("Disattivare la ripetizione e rimuovere il rinvio prima del trasferimento")
 if c.execute("SELECT 1 FROM cloudflare_private_fingerprints WHERE private_item_id=?",(i,)).fetchone():fail("Impegno proveniente da email: il trasferimento richiede la gestione della provenienza")
 tid=c.execute("""INSERT INTO tasks(title,description,kind,priority,status,due_at,owner_id,scope,labels)
 VALUES(?,?,?,?,?,?,?,'personal','[]')""",(t["title"],t["description"],"appointment" if t["kind"]=="appointment" else "task","critical" if t["priority"]=="urgent" else t["priority"],t["status"],t["due_at"],uid)).lastrowid
 c.execute("DELETE FROM private_items WHERE id=? AND owner_id=?",(i,uid))
 c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",(uid,"move_from_private","task",tid))
 return {"id":tid}

def candidates(c,uid,identity,data):
 cfg=cloudflare_mail.load_config(data)
 senders=cloudflare_mail.sender_addresses(cfg.get("private_sender","")) if cfg.get("private_owner_id")==uid and cfg.get("private_identity")==identity else []
 groups=[]
 if senders:
  for r in c.execute("""SELECT source_digest,MIN(received_at) AS received_at,COUNT(*) AS count FROM cloudflare_mail_inbox
   WHERE area='work' AND sender IN ("""+",".join("?" for _ in senders)+""") GROUP BY source_digest ORDER BY received_at DESC LIMIT 200""",senders):
   reason,rows,links=mail_group(c,uid,identity,senders,r["source_digest"])
   groups.append({"digest":r["source_digest"],"received_at":r["received_at"],"titles":[t["title"] for t in rows],"reason":reason})
 items=[]
 for t in c.execute("SELECT * FROM tasks WHERE owner_id=? AND scope='personal' ORDER BY id DESC LIMIT 500",(uid,)):
  if c.execute("SELECT 1 FROM cloudflare_mail_tasks WHERE task_id=?",(t["id"],)).fetchone():continue
  items.append({"id":t["id"],"title":t["title"],"reason":eligible(c,t)})
 return {"mail":groups,"tasks":items}

def mail_group(c,uid,identity,senders,digest):
 source=c.execute("SELECT * FROM cloudflare_mail_inbox WHERE area='work' AND source_digest=?",(digest,)).fetchall()
 links=c.execute("""SELECT l.* FROM cloudflare_mail_tasks l JOIN cloudflare_mail_inbox i ON i.message_hash=l.message_hash
 WHERE i.area='work' AND i.source_digest=?""",(digest,)).fetchall()
 rows=[]
 for l in links:
  t=c.execute("SELECT * FROM tasks WHERE id=? AND owner_id=?",(l["task_id"],uid)).fetchone()
  if t and not any(x["id"]==t["id"] for x in rows):rows.append(t)
 if not source or any(r["sender"] not in senders or r["status"] in ("queued","retry","processing") for r in source):return "Mittenti misti o messaggio non elaborato",rows,links
 if not links or any(not l["task_id"] or not any(t["id"]==l["task_id"] for t in rows) for l in links):return "Non tutti gli impegni originali sono disponibili",rows,links
 for t in rows:
  reason=eligible(c,t,True)
  if reason:return reason,rows,links
  if c.execute("""SELECT 1 FROM cloudflare_mail_tasks l JOIN cloudflare_mail_inbox i ON i.message_hash=l.message_hash WHERE l.task_id=? AND i.source_digest!=?""",(t["id"],digest)).fetchone():return "Impegno collegato ad altri messaggi",rows,links
 new_digest=hashlib.sha256(("private:"+identity+":"+digest).encode()).hexdigest()
 if c.execute("SELECT 1 FROM cloudflare_mail_inbox WHERE area='private' AND source_digest=?",(new_digest,)).fetchone():return "Email già acquisita nell'area personale: verificare manualmente",rows,links
 if table(c,"automatic_ics_queue") and c.execute("SELECT 1 FROM automatic_ics_queue WHERE source_digest=? AND status IN ('queued','sending')",(digest,)).fetchone():return "Invio calendario in corso: attendere",rows,links
 return None,rows,links

def move_mail(c,uid,identity,data,digest):
 cfg=cloudflare_mail.load_config(data)
 if cfg.get("private_owner_id")!=uid or cfg.get("private_identity")!=identity:fail("Configurare prima i mittenti personali",403)
 senders=cloudflare_mail.sender_addresses(cfg.get("private_sender",""))
 reason,rows,links=mail_group(c,uid,identity,senders,digest)
 if reason:fail(reason)
 ids={t["id"]:private_items.create(c,uid,payload(t)) for t in rows}
 for l in links:
  fp=hashlib.sha256(("private:"+identity+":"+l["fingerprint"]).encode()).hexdigest()
  if c.execute("SELECT 1 FROM cloudflare_private_fingerprints WHERE fingerprint=?",(fp,)).fetchone():fail("Possibile duplicato personale")
  c.execute("INSERT INTO cloudflare_private_fingerprints VALUES(?,?,?)",(fp,l["message_hash"],ids[l["task_id"]]))
  c.execute("DELETE FROM cloudflare_mail_tasks WHERE fingerprint=?",(l["fingerprint"],))
 new_digest=hashlib.sha256(("private:"+identity+":"+digest).encode()).hexdigest()
 c.execute("UPDATE cloudflare_mail_inbox SET area='private',private_owner=?,private_identity=?,source_digest=? WHERE area='work' AND source_digest=?",(uid,identity,new_digest,digest))
 for tid in ids:
  c.execute("DELETE FROM tasks WHERE id=?",(tid,))
  c.execute("INSERT INTO audit(actor_id,action,object_type,object_id) VALUES(?,?,?,?)",(uid,"move_to_private","task",tid))
 return {"moved":len(ids)}
