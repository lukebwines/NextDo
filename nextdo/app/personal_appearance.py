"""Private personal dashboard preferences shared by Web and Android."""
import base64
from fastapi import HTTPException
from .personal_travel_tools import photo

THEMES=("dark","light")
PALETTES=("ocean","forest","sunset","lavender")
BACKGROUNDS=("gradient","plain","photo")
DEFAULT={"theme":"dark","palette":"ocean","background":"gradient","photo":None}

def ensure(c):
 c.execute("CREATE TABLE IF NOT EXISTS personal_appearance(owner TEXT PRIMARY KEY,theme TEXT NOT NULL,palette TEXT NOT NULL,background TEXT NOT NULL,photo TEXT)")

def get(c,owner):
 row=c.execute("SELECT theme,palette,background,photo FROM personal_appearance WHERE owner=?",(owner,)).fetchone()
 return dict(row) if row else dict(DEFAULT)

def save(c,owner,body):
 if not isinstance(body,dict) or set(body)-{"theme","palette","background","clear_photo"}:
  raise HTTPException(400,"Preferenze non valide")
 old=get(c,owner)
 theme=body.get("theme",old["theme"]);palette=body.get("palette",old["palette"]);background=body.get("background",old["background"])
 clear=body.get("clear_photo",False)
 if theme not in THEMES or palette not in PALETTES or background not in BACKGROUNDS or type(clear) is not bool:
  raise HTTPException(400,"Preferenze non valide")
 jpeg=None if clear else old["photo"]
 if background=="photo" and not jpeg:
  if not clear:raise HTTPException(400,"Carica prima una fotografia")
  background="gradient"
 c.execute("INSERT OR REPLACE INTO personal_appearance(owner,theme,palette,background,photo) VALUES(?,?,?,?,?)",(owner,theme,palette,background,jpeg))
 return get(c,owner)

def save_photo(c,owner,raw):
 jpeg=photo(raw)["jpeg"]
 old=get(c,owner)
 c.execute("INSERT OR REPLACE INTO personal_appearance(owner,theme,palette,background,photo) VALUES(?,?,?,?,?)",(owner,old["theme"],old["palette"],"photo",jpeg))
 return get(c,owner)

def decode_mobile_photo(body):
 value=body.get("image")
 if set(body)!={"image"} or not isinstance(value,str) or len(value)>7_000_000:
  raise HTTPException(400,"Foto non valida o oltre 5 MB")
 try:raw=base64.b64decode(value,validate=True)
 except (ValueError,TypeError):raise HTTPException(400,"Foto non valida")
 return raw
