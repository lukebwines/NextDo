import time
from test_workspace import init
from test_personal_trips import sample

def test_diary_recorder_and_deduplication(tmp_path):
    c,h=init(tmp_path);p="/api/personal";m="/api/mobile/v1"
    assert c.post(p+"/unlock",headers=h,json={"pin":"123456","confirm":"123456"}).status_code==200
    raw,manifest=sample()
    assert c.post(p+"/trips/import",headers=h,files={"file":("test.zip",raw,"application/zip")}).status_code==200
    tid=manifest["trip"]["id"];web=p+"/trips/"+tid+"/diary";mobile=m+"/trips/"+tid+"/diary/points"
    def pair():
        code=c.post(p+"/mobile/pair",headers=h).json()["code"]
        d=c.post(m+"/pair",json={"code":code}).json()
        s=c.post(m+"/unlock",headers={"Authorization":"Bearer "+d["device_token"]},json={"pin":"123456"}).json()
        return d["device_id"],{"Authorization":"Bearer "+s["session_token"]}
    did,session=pair();other,other_session=pair()
    pt={"id":"a","segment":"s","timestamp":int(time.time()*1000),"latitude":45.0,"longitude":10.0,"accuracy":10.0}
    assert c.post(mobile,headers=session,json={"points":[pt]}).status_code==403
    assert c.post(web+"/recorder",headers=h,json={"device_id":did}).status_code==200
    assert c.post(mobile,headers=other_session,json={"points":[pt]}).status_code==403
    assert c.post(mobile,headers=session,json={"points":[dict(pt,latitude=100)]}).status_code==400
    for _ in range(2):
        assert c.post(mobile,headers=session,json={"points":[pt]}).status_code==200
    assert len(c.get(web).json()["points"])==1
    assert c.post(web+"/clear",headers=h).status_code==200
    assert c.get(web).json()["points"]==[]
    assert c.post(mobile,headers=session,json={"points":[pt]}).status_code==403
    c.close()
