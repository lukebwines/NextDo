"""Read-only RFC 5545 snapshot export. No network calls or calendar synchronization."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import re
from urllib.parse import urlsplit

DATE_ONLY=re.compile(r"\d{4}-\d{2}-\d{2}\Z")
def escaped(value):
 return str(value or "").replace("\\","\\\\").replace("\r\n","\n").replace("\r","\n").replace("\n","\\n").replace(";","\\;").replace(",","\\,").replace("\x00","")

def fold(line):
 # RFC 5545 limit is octets, not Unicode characters. Never split UTF-8 codepoints.
 parts=[];part="";size=0
 for char in line:
  n=len(char.encode("utf-8"))
  if size+n>75:
   parts.append(part);part=" ";size=1
  part+=char;size+=n
 parts.append(part)
 return "\r\n".join(parts)

def utc_value(dt):
 return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def parse_due(raw,tz):
 if not raw:raise ValueError("Data assente")
 if DATE_ONLY.fullmatch(raw):return date.fromisoformat(raw)
 dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
 if dt.tzinfo is None:
  # Naive times from legacy imports are local to NextDo; reject ambiguous or nonexistent times.
  a=dt.replace(tzinfo=tz,fold=0);b=dt.replace(tzinfo=tz,fold=1)
  if a.utcoffset()!=b.utcoffset():raise ValueError("Orario locale ambiguo o inesistente: verificare l'orario")
  dt=a
 return dt

def eligible(task,tz):
 if task["kind"] not in ("task","appointment") or task["status"]=="review":return False
 try:parse_due(task["due_at"],tz);return True
 except (ValueError,TypeError,OverflowError):return False

def explicit_field(desc,label):
 # Use only a dedicated field, never guess a location or pick an arbitrary link from an email.
 match=re.search(r"(?im)^\s*"+label+r"\s*:\s*([^\r\n]+)",desc)
 if not match:return ""
 value=match[1].strip()
 return "" if value.startswith("[") else value

def meeting_link(desc):
 value=explicit_field(desc,r"(?:Collegamento|Link (?:Zoom|Teams|riunione)|URL)")
 if not value or len(value)>1000 or re.search(r"[\s\x00-\x1f\x7f]",value):return ""
 try:
  uri=urlsplit(value)
  if uri.scheme not in ("https","http") or not uri.hostname or uri.username or uri.password:return ""
 except ValueError:return ""
 return value

def calendar(tasks,tz,include_details=False,now=None):
 stamp=utc_value(now or datetime.now(timezone.utc))
 lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//NextDo//Calendar export//IT","CALSCALE:GREGORIAN","METHOD:PUBLISH"]
 for task in tasks:
  due=parse_due(task["due_at"],tz)
  appointment=task["kind"]=="appointment"
  # All-day deadlines, timed confirmed appointments, date-only appointments marked explicitly.
  timed=appointment and isinstance(due,datetime)
  day=due.astimezone(tz).date() if isinstance(due,datetime) else due
  uid=hashlib.sha256(f'{task["id"]}|{task["created_at"]}|{task["owner_id"]}'.encode()).hexdigest()+"@nextdo.invalid"
  title=task["title"]
  if not appointment:title="Scadenza — "+title
  elif not timed:title=title+" (orario da definire)"
  lines.extend(["BEGIN:VEVENT","UID:"+uid,"DTSTAMP:"+stamp,"SUMMARY:"+escaped(title)])
  if timed:
   lines.append("DTSTART:"+utc_value(due))
   # A start is known; no invented duration or end.
  else:
   lines.extend(["DTSTART;VALUE=DATE:"+day.strftime("%Y%m%d"),"DTEND;VALUE=DATE:"+(day+timedelta(days=1)).strftime("%Y%m%d")])
  lines.append("TRANSP:OPAQUE" if timed else "TRANSP:TRANSPARENT")
  desc="Appuntamento NextDo" if appointment else "Scadenza NextDo"
  if appointment and not timed:desc+="\nOrario non definito."
  if not appointment and isinstance(due,datetime):
   desc+="\nData/ora registrata in NextDo: "+due.astimezone(tz).strftime("%d/%m/%Y %H:%M")
  if include_details:
   original=task["description"] or ""
   if original:desc+="\n\n"+original
   place=explicit_field(original,r"(?:Luogo|Sede)")
   if place:lines.append("LOCATION:"+escaped(place))
   link=meeting_link(original)
   if link:lines.append("URL:"+link)
  lines.extend(["DESCRIPTION:"+escaped(desc),"END:VEVENT"])
 lines.append("END:VCALENDAR")
 return "\r\n".join(fold(line) for line in lines)+"\r\n"
