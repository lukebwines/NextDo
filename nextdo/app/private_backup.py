"""Protect private agenda data in the administrative database backup."""
from fastapi import HTTPException

def table(c,n):
 return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(n,)).fetchone() is not None

def identities(c):
 if not table(c,"personal_identities"):return {}
 return dict(c.execute("SELECT user_id,owner FROM personal_identities"))

def owners(c):
 result=set()
 if table(c,"private_items"):result.update(r[0] for r in c.execute("SELECT DISTINCT owner_id FROM private_items"))
 if table(c,"cloudflare_mail_inbox") and "area" in {r[1] for r in c.execute("PRAGMA table_info(cloudflare_mail_inbox)")}:
  result.update(r[0] for r in c.execute("SELECT DISTINCT private_owner FROM cloudflare_mail_inbox WHERE area='private'"))
 return result

def authorize(c,app,req,uid):
 ids=owners(c)
 if not ids:return
 if ids!={uid}:raise HTTPException(403,"Il backup contiene dati personali di altri account. Usare il backup protetto di Home Assistant.")
 unlock=getattr(app.state,"personal_backup_authorize",None)
 if not unlock:raise HTTPException(423,"Accesso personale non disponibile")
 identity=unlock(req)
 if identities(c).get(uid)!=identity:raise HTTPException(403,"Identità personale non corrispondente")
