"""Controlled import of UO SEGR CDS annual teaching calendar (xlsx, no third-party parser).

The uploaded workbook is parsed in memory. Preview and final selection are re-evaluated
from the same uploaded bytes; nothing is imported until the admin explicitly selects IDs.
"""
from __future__ import annotations
import hashlib
import io
import json
import posixpath
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone,date
from zoneinfo import ZoneInfo
from fastapi import HTTPException,Request,UploadFile,File,Form

MAIN="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKGREL="http://schemas.openxmlformats.org/package/2006/relationships"
MAX_BYTES=8*1024*1024
EXPECTED=["Macro Processo","Sotto Processo","indicativamente a partire da","SCADENZE","A.A. di riferimento ","Attività ","Destinatario attività","Responsabile attività","Ufficio di riferimento per il supporto","Organo deliberante","Atto amministrativo"]
ROLES=("responsabile","supporto","destinatario")
ROME=ZoneInfo("Europe/Rome")

def reject(message,code=400):
 raise HTTPException(status_code=code,detail=message)

def textval(value):
 return str(value or "").strip()

def normalize(value):
 return re.sub(r"\s+"," ",textval(value)).casefold()

def msdate(value):
 if value is None or textval(value)=="":
  return ""
 try:
  number=float(value)
  if number<1 or number>120000:raise ValueError()
  return (datetime(1899,12,30)+timedelta(days=number)).date().isoformat()
 except (ValueError,TypeError,OverflowError):
  try:return date.fromisoformat(textval(value)[:10]).isoformat()
  except ValueError:return ""

def parse_xlsx(raw):
 try:
  book=zipfile.ZipFile(io.BytesIO(raw))
 except (zipfile.BadZipFile,ValueError):
  reject("Il file non è un Excel xlsx valido")
 with book:
  if len(book.infolist())>200 or sum(i.file_size for i in book.infolist())>50*1024*1024:
   reject("Il file Excel supera i limiti di sicurezza",413)
  try:
   wb=ET.fromstring(book.read("xl/workbook.xml"))
   rels=ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
  except (KeyError,ET.ParseError):
   reject("Struttura del file Excel incompleta")
  sheet=next((s for s in wb.findall("{%s}sheets/{%s}sheet"%(MAIN,MAIN))
              if s.get("name")=="Programmazione didattica"),None)
  if sheet is None:reject("Foglio Programmazione didattica non presente: verificare il calendario ufficiale")
  targetmap={r.get("Id"):r.get("Target") for r in rels.findall("{%s}Relationship"%PKGREL)}
  target=targetmap.get(sheet.get("{%s}id"%REL),"")
  path=posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join("xl",target))
  if not path.startswith("xl/worksheets/"):reject("Percorso del foglio Excel inatteso")
  strings=[]
  if "xl/sharedStrings.xml" in book.namelist():
   root=ET.fromstring(book.read("xl/sharedStrings.xml"))
   for si in root.findall("{%s}si"%MAIN):
    strings.append("".join(t.text or "" for t in si.iter("{%s}t"%MAIN)))
  try:root=ET.fromstring(book.read(path))
  except (KeyError,ET.ParseError):reject("Il foglio Programmazione didattica non è leggibile")
  output=[]
  for row in root.findall(".//{%s}sheetData/{%s}row"%(MAIN,MAIN)):
   ix=int(row.get("r","0"))
   if ix>10000:reject("Troppi record nel calendario",413)
   cells={}
   for cell in row.findall("{%s}c"%MAIN):
    address=cell.get("r","")
    match=re.match(r"^([A-Z]+)\d+$",address)
    if not match:continue
    col=match.group(1)
    if len(col)!=1 or col>"K":continue
    rawval=cell.find("{%s}v"%MAIN)
    value=rawval.text if rawval is not None else None
    if cell.get("t")=="s" and value is not None:
     try:value=strings[int(value)]
     except (ValueError,IndexError):value=""
    elif cell.get("t")=="inlineStr":
     inner=cell.find("{%s}is"%MAIN)
     value="".join(e.text or "" for e in inner.iter("{%s}t"%MAIN)) if inner is not None else ""
    cells[ord(col)-65]=value
   if ix==1:
    headers=[textval(cells.get(j)) for j in range(11)]
    if [normalize(x) for x in headers]!=[normalize(x) for x in EXPECTED]:
     reject("Intestazioni del calendario diverse dal tracciato verificato: importazione interrotta")
    continue
   rowvals=[cells.get(j) for j in range(11)]
   output.append((ix,rowvals))
  return output

def parse_calendar(raw,filename):
 if len(raw)>MAX_BYTES:reject("File troppo grande",413)
 if not filename.lower().endswith(".xlsx"):reject("Caricare il calendario originale in formato .xlsx")
 rows=parse_xlsx(raw)
 result=[]
 seen=set()
 for line,v in rows:
  title=textval(v[5])
  if not title:continue
  role_cells={"destinatario":textval(v[6]),"responsabile":textval(v[7]),"supporto":textval(v[8])}
  roles=[role for role in ROLES if re.search(r"\bUO\s+SEGR\s+CDS\b",role_cells[role],re.I)]
  if not roles:continue
  academic=textval(v[4]);process=textval(v[1])
  # Stable across reimport and date changes; does not reuse fixture/example IDs.
  key=hashlib.sha256(("nextdo-calendario-v1|"+normalize(academic)+"|"+
                      normalize(process)+"|"+normalize(title)).encode("utf-8")).hexdigest()
  if key in seen:reject("Attività duplicata nel file di origine: riga "+str(line))
  seen.add(key)
  start=msdate(v[2]);due=msdate(v[3])
  invalid=bool(start and due and start>due)
  result.append({
   "key":key,"row_number":line,"title":title,"year":academic,"process":process,
   "macro_process":textval(v[0]),"start":start,"due":due,
   "recipient":role_cells["destinatario"],"responsible":role_cells["responsabile"],
   "support":role_cells["supporto"],"roles":roles,
   "deliberating_body":textval(v[9]),"administrative_act":textval(v[10]),
   "indicative":True,"invalid_dates":invalid,
   "past":bool(due and due<date.today().isoformat()),
   "requires_verification":invalid or not due or not academic
  })
 if len(result)>250:reject("Troppe attività pertinenti: verificare il tracciato",413)
 return result

def timestamp(day):
 if not day:return None
 d=date.fromisoformat(day)
 return datetime(d.year,d.month,d.day,12,tzinfo=ROME).astimezone(timezone.utc).isoformat()

def ensure_table(c):
 c.execute("""CREATE TABLE IF NOT EXISTS imported_calendar (
   source_key TEXT PRIMARY KEY,task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
   academic_year TEXT NOT NULL,source_file TEXT NOT NULL,
   imported_due TEXT,imported_start TEXT,
   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

def augment_existing(c,rows):
 ensure_table(c)
 for r in rows:
  existing=c.execute("SELECT task_id,imported_due,imported_start FROM imported_calendar WHERE source_key=?",(r["key"],)).fetchone()
  r["imported_task_id"]=existing["task_id"] if existing else None
  r["already_imported"]=bool(existing and existing["task_id"] is not None)
  r["changed_in_source"]=bool(existing and
     (existing["imported_due"]!=r["due"] or existing["imported_start"]!=r["start"]))
  r["select_by_default"]=not r["already_imported"] and not r["past"] and not r["requires_verification"]
 return rows

def register_routes(app,*,conn,user,csrf,record):
 def admin(req):
  u=user(req)
  if u["role"]!="admin":reject("Solo gli amministratori possono importare il calendario",403)
  return u

 @app.post("/api/calendar-import/preview")
 async def preview_calendar(req:Request,file:UploadFile=File(...)):
  admin(req);csrf(req)
  raw=await file.read(MAX_BYTES+1)
  rows=parse_calendar(raw,file.filename or "")
  with conn() as c:rows=augment_existing(c,rows)
  return {"source_file":file.filename,"total":len(rows),"rows":rows}

 @app.post("/api/calendar-import/apply")
 async def apply_calendar(req:Request,file:UploadFile=File(...),selected: str=Form(...)):
  u=admin(req);csrf(req)
  try:ids=json.loads(selected)
  except (ValueError,TypeError):reject("Selezione non valida")
  if not isinstance(ids,list) or len(ids)>250 or any(not isinstance(x,str) or len(x)!=64 for x in ids) or len(set(ids))!=len(ids):
   reject("Selezione non valida")
  if not ids:return {"created":0,"skipped":0,"warnings":[]}
  rows=parse_calendar(await file.read(MAX_BYTES+1),file.filename or "")
  selected_set=set(ids)
  if not selected_set.issubset({r["key"] for r in rows}):reject("Le attività selezionate non corrispondono al file")
  selected_rows=[r for r in rows if r["key"] in selected_set]
  if any(r["invalid_dates"] for r in selected_rows):
   reject("Correggere le righe con data iniziale successiva alla scadenza")
  created=0;skipped=0
  filename=(file.filename or "calendario.xlsx").split("/")[-1].split("\\")[-1][:160]
  with conn() as c:
   ensure_table(c)
   for r in selected_rows:
    old=c.execute("SELECT task_id FROM imported_calendar WHERE source_key=?",(r["key"],)).fetchone()
    if old and old["task_id"] is not None:
     skipped+=1
     continue
    summary=[
     "Fonte: "+filename+" — foglio Programmazione didattica, riga "+str(r["row_number"]),
     "Titolo originale completo: "+r["title"],
     "Anno accademico: "+(r["year"] or "[DA VERIFICARE]"),
     "Macroprocesso: "+(r["macro_process"] or "[DA VERIFICARE]"),
     "Sottoprocesso: "+(r["process"] or "[DA VERIFICARE]"),
     "Ruolo UO SEGR CDS: "+", ".join(r["roles"]),
     "Responsabile indicato nella fonte: "+(r["responsible"] or "[DA VERIFICARE]"),
     "Supporto: "+(r["support"] or "[DA VERIFICARE]"),
     "Destinatario: "+(r["recipient"] or "[DA VERIFICARE]"),
     "Organo deliberante: "+(r["deliberating_body"] or "[DA VERIFICARE]"),
     "Atto amministrativo: "+(r["administrative_act"] or "[DA VERIFICARE]"),
     "Date indicative: sì. Verificare lo stato effettivo prima di assegnare ai colleghi.",
     "CdS e collega incaricato: [DA VERIFICARE]"
    ]
    labels=["UO SEGR CDS","Calendario offerta formativa"]
    if r["process"]:labels.append(r["process"][:60])
    # Imported tasks are private to the administrator until the scope is validated.
    # Never infer that a past deadline is uncompleted: mark as waiting for review.
    status="waiting" if r["past"] or r["requires_verification"] else "todo"
    tid=c.execute("""INSERT INTO tasks(
      title,description,kind,priority,status,due_at,start_at,owner_id,assigned_to,
      group_id,completion_mode,display_enabled,recurrence,labels,scope,project_id)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (r["title"][:250],"\n".join(summary),"task","normal",status,
       timestamp(r["due"]),timestamp(r["start"]),u["id"],None,
       None,"global",0,"none",json.dumps(labels,ensure_ascii=False),"personal",None)).lastrowid
    c.execute("""INSERT INTO imported_calendar(source_key,task_id,academic_year,source_file,imported_due,imported_start)
      VALUES(?,?,?,?,?,?) ON CONFLICT(source_key) DO UPDATE SET
      task_id=excluded.task_id,academic_year=excluded.academic_year,source_file=excluded.source_file,
      imported_due=excluded.imported_due,imported_start=excluded.imported_start""",
      (r["key"],tid,r["year"],filename,r["due"],r["start"]))
    record(c,u["id"],"calendar_import","task",tid)
    created+=1
  return {"created":created,"skipped":skipped,
          "warnings":["Le scadenze sono indicative. Verificare l'effettiva situazione prima di assegnarle."]}
