"""Conservative local suggestions; never save or query Airportia before confirmation."""
from datetime import date
import re
from .personal_travel_tools import pdf_text

FLIGHT=re.compile(r"(?<![A-Z0-9])(?:[A-Z]{2}|[A-Z][0-9]|[0-9][A-Z])\s?[0-9]{1,4}[A-Z]?(?![A-Z0-9])")
MONTHS={}
for i,names in enumerate(("gen gennaio jan january","feb febbraio february","mar marzo march","apr aprile april","mag maggio may","giu giugno jun june","lug luglio jul july","ago agosto aug august","set sett settembre sep sept september","ott ottobre oct october","nov novembre november","dic dicembre dec december"),1):
 for name in names.split():MONTHS[name]=i
MONTH=re.compile(r"\b(\d{1,2})\s+("+"|".join(sorted(MONTHS,key=len,reverse=True))+r")\.?(?:\s+(\d{4}))?\b",re.I)
NUMDATE=re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b")
AIRPORT=re.compile(r"\b([A-Z]{3})\b(?=\s*(?:\)|\d{1,2}:\d{2}|$))")
DIRECT=re.compile(r"\b([A-Z]{3})\s*(?:→|->|–|—|-|to)\s*([A-Z]{3})\b")

def dates(text,trip):
 found=[]
 def add(y,m,d):
  try:found.append(date(int(y),int(m),int(d)).isoformat())
  except (ValueError,TypeError):pass
 for match in NUMDATE.finditer(text):
  v=match.group(1)
  if "/" in v:
   d,m,y=v.split("/");add(y,m,d)
  else:
   y,m,d=v.split("-");add(y,m,d)
 try:start=date.fromisoformat(trip["start"]);end=date.fromisoformat(trip["end"])
 except (KeyError,ValueError,TypeError):start=end=None
 for match in MONTH.finditer(text):
  d,m,y=match.groups();m=MONTHS[m.lower()]
  if y:add(y,m,d)
  elif start and end and end.year-start.year<=2:
   valid=[]
   for year in range(start.year,end.year+1):
    try:
     candidate=date(year,m,int(d))
     if start<=candidate<=end:valid.append(candidate.isoformat())
    except ValueError:pass
   if len(valid)==1:found.extend(valid)
 return list(dict.fromkeys(found))

def route(text):
 direct=list(DIRECT.finditer(text))
 if len(direct)==1:return direct[0].groups()
 parts=re.split(r"→|->",text)
 if len(parts)!=2:return "",""
 def one(part):
  part=part.split(";")[0].strip()
  codes=list(dict.fromkeys(AIRPORT.findall(part)))
  return codes[0] if len(codes)==1 else ""
 return one(parts[0]),one(parts[1])

def candidates(text,trip,summary=False):
 numbers=list(dict.fromkeys(re.sub(r"\s+","",m.group()) for m in FLIGHT.finditer(text)))
 if not numbers or len(numbers)>8:return []
 # A PDF line must contain route/date evidence, not merely a reference-like token.
 o,a=route(text)
 ds=dates(text,trip)
 if not summary and not (o or a or ds):return []
 # For an itinerary summary, the date before the route is the first departure only.
 before=re.split(r"→|->",text,maxsplit=1)[0]
 first=dates(before,trip)
 d=first[0] if len(first)==1 else ds[0] if len(ds)==1 else ""
 if len(numbers)==1:
  return [{"number":numbers[0],"date":d,"from":o,"to":a}]
 # Whole-journey endpoints are not the intermediate airports.
 # Never assign the whole journey's arrival or date to every segment.
 return [{"number":n,"date":d if i==0 else "","from":o if i==0 else "","to":a if i==len(numbers)-1 else ""} for i,n in enumerate(numbers)]

def suggest(booking,trip,files,legacy=None):
 if "flight_segments" in booking:return []
 proposed=[];conflicts=set()
 def merge(row):
  same=[x for x in proposed if x["number"]==row["number"]]
  exact=[x for x in same if x["date"] and x["date"]==row["date"]]
  compatible=exact or [x for x in same if not x["date"] or not row["date"]]
  if len(compatible)>1:return
  if not compatible:
   if len(proposed)<8:proposed.append(dict(row))
   return
  target=compatible[0]
  for k in ("date","from","to"):
   key=(id(target),k)
   if key in conflicts:continue
   v=row[k]
   if target[k] and v and target[k]!=v:
    target[k]="";conflicts.add(key)
   elif v and not target[k]:target[k]=v
 if legacy:merge(dict(zip(("number","date","from","to"),legacy)))
 # Only flight-related booking fields, excluding passenger names, booking references, etc.
 for pair in booking.get("lines",[])+booking.get("fields",[]):
  if not isinstance(pair,list) or len(pair)!=2:continue
  label,value=pair
  if not isinstance(label,str) or not isinstance(value,str):continue
  if not re.search(r"\bandata\b|\britorno\b|\btratta\b|\bvol[oi]\b|\bflight\b|\boutbound\b|\binbound\b",label,re.I):continue
  if re.search(r"bagagl|baggage|check.?in|status|stato|attenzione|warning|riferimento",label,re.I):continue
  for row in candidates(value[:2000],trip,summary=True):merge(row)
 # Read only this booking's attached PDFs locally; no external AI or file upload.
 names=[booking.get("doc")]+[x.get("file") for x in booking.get("attachments",[]) if isinstance(x,dict)]
 pdf_read=0;pdf_skipped=False;pdf_bytes=0
 for name in list(dict.fromkeys(n for n in names if isinstance(n,str)))[:3]:
  raw=files.get(name)
  if not isinstance(raw,bytes):continue
  if len(raw)>2*1024*1024 or pdf_bytes+len(raw)>4*1024*1024:
   pdf_skipped=True;continue
  pdf_bytes+=len(raw)
  try:text=pdf_text(raw);pdf_read+=1
  except Exception:pdf_skipped=True;continue
  for line in text.splitlines()[:300]:
   # Do not combine disconnected PDF lines or infer a stop from a city name.
   for row in candidates(line[:1000],trip):merge(row)
 return {"segments":proposed,"pdf_read":pdf_read,"pdf_skipped":pdf_skipped}
