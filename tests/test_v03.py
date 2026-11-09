import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from backend.memory import extract_wram,pair_compare,candidate_report,breakpoint_plan,WRAM_SIZE
from backend.storage import Store

def test_extract_wram_and_mirroring():
    a=bytes([13])*WRAM_SIZE
    assert extract_wram(a)==a
    full=bytearray(0x1000000); full[0x7e0000:0x800000]=a
    assert extract_wram(bytes(full))==a
    import pytest
    with pytest.raises(ValueError):extract_wram(b'bad')

def test_compare_and_candidates():
    a=bytearray(WRAM_SIZE);b=bytearray(WRAM_SIZE)
    a[0x36d0]=11;b[0x36d0]=22
    a[0x52c8]=11;b[0x52c8]=22
    d=pair_compare(bytes(a),bytes(b),0x36c0,32)
    assert d['different_bytes']==1 and d['entries'][0]['address']=='7E:36D0'
    shots=[{'id':'a','filename':'a','character':'Sheeva','expected_id':11,'data':bytes(a)}, {'id':'b','filename':'b','character':'Smoke','expected_id':22,'data':bytes(b)}]
    c=candidate_report(shots)
    assert c['count']==2 and {x['offset'] for x in c['results']}=={0x36d0,0x52c8}
    assert c['results'][0]['matches_expected']==2
    assert breakpoint_plan([0x36d0])[0]['address']=='7E:36D0'

def test_repeat_snapshot_rejects_unstable():
    a=bytearray(WRAM_SIZE);b=bytearray(WRAM_SIZE);c=bytearray(WRAM_SIZE)
    a[100]=1;b[100]=2;c[100]=3
    a[0x36d0]=b[0x36d0]=11;c[0x36d0]=22
    shots=[{'id':str(i),'filename':str(i),'character':k,'expected_id':None,'data':bytes(v)} for i,(k,v) in enumerate([('Sheeva',a),('Sheeva',b),('Smoke',c)])]
    out=candidate_report(shots)
    assert all(x['offset']!=100 for x in out['results'])
    assert any(x['offset']==0x36d0 for x in out['results'])

def test_capture_api_persistence(monkeypatch):
    import backend.server as s
    with tempfile.TemporaryDirectory() as root:
        monkeypatch.setattr(s,'store',Store(root)); monkeypatch.setattr(s,'session',s.Session())
        c=TestClient(s.app)
        pid=c.post('/api/projects',json={'name':'Fase3'}).json()['id']
        raw=bytearray(WRAM_SIZE);raw[0x36d0]=11
        def upload(name,expected,contents):
            return c.post('/api/captures',data={'character':name,'expected_id':expected},files={'file':(name+'.dmp',bytes(contents))})
        resp=upload('Sheeva','0B',raw);assert resp.status_code==200,resp.text
        left=resp.json()['id'];raw[0x36d0]=22
        right=upload('Human Smoke','16',raw).json()['id']
        assert len(c.get('/api/captures').json())==2
        d=c.get('/api/captures/compare',params={'left':left,'right':right,'offset':0x36d0,'length':1}).json()
        assert d['different_bytes']==1
        res=c.post('/api/captures/candidates',json={'ids':[left,right]}).json()
        assert any(x['address']=='7E:36D0' for x in res['results'])
        assert c.post(f'/api/projects/{pid}/open').status_code==200
        assert len(c.get('/api/captures').json())==2
        assert c.delete('/api/captures/'+left).status_code==200
        assert len(c.get('/api/captures').json())==1

def test_real_snapshots_when_present():
    files=list(Path('/mnt/data').glob('JADE.dmp'))
    if not files:return
    jade=extract_wram(files[0].read_bytes())
    assert jade[0x36d0]==0x10 and jade[0x52c8]==0x10
