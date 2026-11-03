"""Verify asset cache busting for the Home Assistant Ingress interface."""
import importlib,os,sys
from fastapi.testclient import TestClient

def test_html_does_not_cache_old_dashboard(tmp_path):
 os.environ['NEXTDO_DATA']=str(tmp_path)
 sys.modules.pop('app.main',None)
 app=importlib.import_module('app.main').app
 with TestClient(app) as client:
  result=client.get('/')
  assert result.status_code==200
  assert 'no-store' in result.headers.get('cache-control','')
  assert 'assets/app.js?v=' in result.text
  assert 'assets/style.css?v=' in result.text
  assert 'assets/visual-v1.css?v=' in result.text
  js=client.get('/assets/app.js')
  assert js.status_code==200
  assert 'no-store' in js.headers.get('cache-control','')
  assert 'Importa backup NextDo' in js.text
  css=client.get('/assets/visual-v1.css')
  assert css.status_code==200
  assert 'dash-metrics' in css.text
  assert client.get('/api/build').status_code==401
