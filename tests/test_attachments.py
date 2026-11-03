"""File-upload tests, with synthetic data only (no real task/course information)."""
import importlib
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def authenticated(tmp_path):
    os.environ['NEXTDO_DATA'] = str(tmp_path)
    sys.modules.pop('app.main', None)
    mod = importlib.import_module('app.main')
    client = TestClient(mod.app)
    headers = {'X-NextDo-CSRF': client.get('/api/csrf').json()['csrf']}
    credentials = {'username': 'tester', 'password': 'passphrase at least 12'}
    setup = dict(credentials, setup_token=(tmp_path / 'setup-token').read_text())
    assert client.post('/api/setup', json=setup, headers=headers).status_code == 200
    assert client.post('/api/login', json=credentials, headers=headers).status_code == 200
    return client, headers


def test_upload_to_new_task_and_note(tmp_path):
    client, headers = authenticated(tmp_path)
    for kind, name, content in [
        ('task', 'example.pdf', b'%PDF-1.7 test document'),
        ('note', 'image.png', b'\x89PNG\r\n\x1a\n fake image'),
        ('task', 'table.xlsx', b'PK\x03\x04 fake workbook'),
        ('note', 'slides.pptx', b'PK\x03\x04 fake slides'),
    ]:
        created = client.post('/api/tasks', headers=headers, json={'title': 'Sample', 'kind': kind})
        assert created.status_code == 200, created.text
        tid = created.json()['id']
        uploaded = client.post('/api/tasks/' + str(tid) + '/attachments', headers=headers,
                               files={'file': (name, content, 'application/octet-stream')})
        assert uploaded.status_code == 200, uploaded.text
        aid = uploaded.json()['id']
        task = client.get('/api/tasks/' + str(tid))
        assert task.status_code == 200
        assert task.json()['attachments'][0]['filename'] == name
        downloaded = client.get('/api/attachments/' + str(aid))
        assert downloaded.status_code == 200
        assert downloaded.content == content
        assert downloaded.headers.get('content-type') == 'application/octet-stream'
        deleted = client.delete('/api/attachments/' + str(aid), headers=headers)
        assert deleted.status_code == 200
        assert client.get('/api/attachments/' + str(aid)).status_code == 404
    client.close()


def test_reject_forbidden_file_and_oversized_upload(tmp_path):
    client, headers = authenticated(tmp_path)
    tid = client.post('/api/tasks', headers=headers, json={'title': 'Sample'}).json()['id']
    invalid = client.post(f'/api/tasks/{tid}/attachments', headers=headers,
                          files={'file': ('script.html', b'<script>demo</script>', 'text/html')})
    assert invalid.status_code == 400
    oversized = client.post(f'/api/tasks/{tid}/attachments', headers=headers,
                            files={'file': ('big.pdf', b'X' * (15*1024*1024+1), 'application/pdf')})
    assert oversized.status_code == 413
    assert client.get(f'/api/tasks/{tid}').json()['attachments'] == []
    assert not list((tmp_path / 'attachments').iterdir())
    client.close()


def test_file_form_styles_and_versioned_assets(tmp_path):
    client, _ = authenticated(tmp_path)
    html = client.get('/')
    assert html.status_code == 200
    assert 'assets/file-tools.js?v=' in html.text
    assert 'assets/file-ui.css?v=' in html.text
    assert html.text.index('assets/file-tools.js') < html.text.index('assets/app.js')
    js = client.get('/assets/app.js').text
    assert "focus:'due'" in js
    assert "focus:'labels'" in js
    assert "focus:'attachments'" in js
    assert 'NextDoFileUI.quickDrop' in js
    helper = client.get('/assets/file-tools.js')
    assert helper.status_code == 200
    assert 'file-drop-zone' in helper.text
    client.close()
