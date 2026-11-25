from test_api import app_client

def test_assistant_link_and_address(tmp_path):
 client,h=app_client(tmp_path)
 assert client.get('/api/assistant-link').status_code==401
 password='passphrase at least 12'
 assert client.post('/api/setup',json={'username':'tester','password':password,'setup_token':(tmp_path/'setup-token').read_text().strip()},headers=h).status_code==200
 assert client.post('/api/login',json={'username':'tester','password':password},headers=h).status_code==200
 assert client.get('/api/assistant-link').json()=={'url':''}
 for bad in ['https://evil.test/c/x','https://chatgpt.com/share/x','https://chatgpt.com/c/x?token=secret','https://chatgpt.com@evil.test/c/x']:
  assert client.post('/api/assistant-link',json={'url':bad},headers=h).status_code==400
 url='https://chatgpt.com/c/example'
 assert client.post('/api/assistant-link',json={'url':url},headers=h).json()=={'url':url}
 assert client.get('/api/assistant-link').json()=={'url':url}
 assert client.post('/api/assistant-link',json={'url':''},headers=h).json()=={'url':''}
 tid=client.post('/api/tasks',json={'title':'Test appointment','kind':'appointment','address':'Via Esempio 1, Roma'},headers=h).json()['id']
 assert client.get('/api/tasks/'+str(tid)).json()['address']=='Via Esempio 1, Roma'
 assert client.put('/api/tasks/'+str(tid),json={'title':'Modified','kind':'appointment'},headers=h).status_code==200
 assert client.get('/api/tasks/'+str(tid)).json()['address']=='Via Esempio 1, Roma'
