import copy
from test_workspace import init,create_user,sign_in
from test_personal_trips import sample

def test_timeline_import(tmp_path):
    c,h=init(tmp_path);p="/api/personal";m="/api/mobile/v1"
    assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
    raw,manifest=sample()
    assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
    tid=manifest["trip"]["id"];web=p+"/trips/"+tid+"/timeline";mobile=m+"/trips/"+tid+"/timeline"
    code=c.post(p+"/mobile/pair",headers=h).json()["code"]
    d=c.post(m+"/pair",json={"code":code}).json()
    s=c.post(m+"/unlock",headers={"Authorization":"Bearer "+d["device_token"]},json={"pin":"123456"}).json()
    session={"Authorization":"Bearer "+s["session_token"]}
    v={"startTime":"2027-01-01T08:00:00-08:00","endTime":"2027-01-01T08:30:00-08:00","location":{"lat":0.1,"lon":0.2}}
    b={"from":"2027-01-01","to":"2027-01-02","visits":[v,v],"activities":[],"paths":[[{"time":"2027-01-01T09:00:00-08:00","lat":0.2,"lon":0.3}]]}
    assert c.post(mobile,json=b).status_code==401
    assert c.get(web).json()["data"] is None
    for _ in range(2):
        r=c.post(mobile,headers=session,json=b);assert r.status_code==200,r.text
    assert len(c.get(web).json()["data"]["visits"])==1
    bad=copy.deepcopy(b);bad["paths"][0][0]["time"]="2026-12-31T09:00:00-08:00"
    assert c.post(mobile,headers=session,json=bad).status_code==400
    bad=copy.deepcopy(b);bad["rawSignals"]=[]
    assert c.post(mobile,headers=session,json=bad).status_code==400
    assert c.post(m+"/trips/not-owned/timeline",headers=session,json=b).status_code==404
    assert c.post(p+"/mobile/devices/"+d["device_id"]+"/revoke",headers=h).status_code==200
    assert c.post(mobile,headers=session,json=b).status_code==401
    assert c.get(web).json()["data"]["paths"]==b["paths"]
    assert c.post(web+"/clear",headers=h).status_code==200
    assert c.get(web).json()["data"] is None
    c.close()
