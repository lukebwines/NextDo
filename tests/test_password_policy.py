"""Role-specific password policy with synthetic accounts."""
from test_workspace import init

def test_colleague_can_use_eight_characters_for_creation_login_change_and_reset(tmp_path):
 c,h=init(tmp_path)
 short=c.post('/api/users',headers=h,json={'username':'short_user','password':'1234567','role':'user'})
 assert short.status_code==422
 created=c.post('/api/users',headers=h,json={'username':'colleague','display_name':'Test Colleague','password':'8charPwd','role':'user'})
 assert created.status_code==200,created.text
 uid=next(u['id'] for u in c.get('/api/users').json() if u['username']=='colleague')
 c.cookies.delete('nextdo_session')
 assert c.post('/api/login',headers=h,json={'username':'colleague','password':'8charPwd'}).status_code==200
 changed=c.post('/api/profile/password',headers=h,json={'current_password':'8charPwd','new_password':'abcd9876'})
 assert changed.status_code==200,changed.text
 assert c.get('/api/profile').status_code==401
 assert c.post('/api/login',headers=h,json={'username':'colleague','password':'abcd9876'}).status_code==200
 assert c.post('/api/profile/password',headers=h,json={'current_password':'abcd9876','new_password':'1234567'}).status_code==422
 c.cookies.delete('nextdo_session')
 assert c.post('/api/login',headers=h,json={'username':'admin','password':'sample admin password 123'}).status_code==200
 assert c.post(f'/api/admin/users/{uid}/password',headers=h,json={'new_password':'reset888'}).status_code==200
 c.cookies.delete('nextdo_session')
 assert c.post('/api/login',headers=h,json={'username':'colleague','password':'reset888'}).status_code==200
 c.close()

def test_admin_minimum_is_twelve_in_every_workflow(tmp_path):
 c,h=init(tmp_path)
 assert c.post('/api/users',headers=h,json={'username':'bad_admin','password':'12345678','role':'admin'}).status_code==400
 assert c.post('/api/users',headers=h,json={'username':'fine_admin','password':'adminlong1234','role':'admin'}).status_code==200
 uid=next(u['id'] for u in c.get('/api/users').json() if u['username']=='fine_admin')
 assert c.post(f'/api/admin/users/{uid}/password',headers=h,json={'new_password':'reset888'}).status_code==400
 assert c.post(f'/api/admin/users/{uid}/password',headers=h,json={'new_password':'adminreset12'}).status_code==200
 assert c.post('/api/profile/password',headers=h,json={'current_password':'sample admin password 123','new_password':'12345678'}).status_code==400
 c.close()

def test_promotion_requires_new_strong_admin_password(tmp_path):
 c,h=init(tmp_path)
 assert c.post('/api/users',headers=h,json={'username':'member','password':'12345678','role':'user'}).status_code==200
 uid=next(u['id'] for u in c.get('/api/users').json() if u['username']=='member')
 target='/api/admin/users/'+str(uid)
 assert c.put(target,headers=h,json={'role':'admin','active':True}).status_code==400
 assert c.put(target,headers=h,json={'role':'admin','active':True,'promotion_password':'short888'}).status_code==400
 assert c.put(target,headers=h,json={'role':'admin','active':True,'promotion_password':'promotedadmin12'}).status_code==200
 c.cookies.delete('nextdo_session')
 assert c.post('/api/login',headers=h,json={'username':'member','password':'12345678'}).status_code==401
 assert c.post('/api/login',headers=h,json={'username':'member','password':'promotedadmin12'}).status_code==200
 assert c.post('/api/profile/password',headers=h,json={'current_password':'promotedadmin12','new_password':'eight888'}).status_code==400
 c.close()
