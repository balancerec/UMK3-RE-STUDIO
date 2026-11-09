import tempfile
from pathlib import Path
from backend.storage import Store
from backend.analysis import build_xrefs
from backend.core import Rom


def test_store_projects_symbols_artifacts():
    with tempfile.TemporaryDirectory() as temp:
        a=Store(temp);p=a.create('Minha Deluxe / Teste');pid=p['id']
        raw=b'abc'*1024
        sha=a.save_artifact(pid,'rom_sha',raw,'game.sfc')
        assert a.load_artifact(sha)==raw
        a.add_symbol(pid,'SnesPrgRom',0x1234,'TEST','not confirmed')
        a.add_symbol(pid,'SnesPrgRom',0x1234,'TEST','not confirmed')
        assert len(a.symbols(pid))==1
        a.observe(pid,0x0B,'SHEEVA',0x7e36d0,0x0b,'SHEEVA.dmp')
        b=Store(temp)
        assert b.get(pid)['rom_sha']==sha
        assert b.observations(pid)[0]['value']==0x0b
        assert len(b.projects())==1


def test_xrefs_direct_jump_and_branch():
    data=bytearray(0x10000)
    # C0:0000 JSL $C00010; C0:0004 BNE $C00008; C0:0006 RTL
    data[:7]=bytes.fromhex('22 10 00 C0 D0 02 6B')
    data[8]=0x6b
    data[16]=0x6b
    r=Rom(bytes(data));r.mapping="hirom"
    a=build_xrefs(r,[0],max_instructions=50)
    assert any(x['kind']=='call' and x['to_offset']==16 for x in a['references'])
    assert any(x['kind']=='branch' and x['to_offset']==8 for x in a['references'])
    assert not a['truncated']


def test_real_rom_hook_if_present():
    files=list(Path('/mnt/data').glob('*SnesPrgRom.dmp'))
    if not files:return
    r=Rom(files[0].read_bytes())
    assert r.read(0x08a53c,4)==bytes.fromhex('5c625ed0')


def test_api_persists_imports_and_symbols(monkeypatch):
    from fastapi.testclient import TestClient
    import backend.server as server
    with tempfile.TemporaryDirectory() as root:
        monkeypatch.setattr(server,'store',Store(root))
        monkeypatch.setattr(server,'session',server.Session())
        client=TestClient(server.app)
        pid=client.post('/api/projects',json={'name':'Deluxe V0.2'}).json()['id']
        raw=bytearray(8*1024*1024)
        raw[0x40ffc0:0x40ffc0+21]=b'SNESFOREVER.COM.BR'.ljust(21,b' ')
        raw[0x40ffd5]=0x35
        raw[0x08a53c:0x08a540]=bytes.fromhex('5c625ed0')
        up=client.post('/api/rom',files={'file':('Deluxe.sfc',bytes(raw))})
        assert up.status_code==200
        assert up.json()['mapping']=='exhirom'
        add=client.post('/api/symbols',json={'type':'SnesPrgRom','address':0x8a53c,'label':'HookCandidate'})
        assert add.status_code==200
        assert client.post('/api/characters/seed').json()['count']==30
        x=client.post('/api/xrefs/analyze',json={'roots':[0x08a53c],'max_instructions':30})
        assert x.status_code==200
        assert any(t['to_offset']==0x105e62 for t in client.get('/api/xrefs').json()['references'])
        assert client.post(f'/api/projects/{pid}/open').status_code==200
        assert client.get('/api/status').json()['ready'] is True
        assert any(t['label']=='HookCandidate' for t in client.get('/api/symbols').json())
        assert len(client.get('/api/characters').json()['observations'])==30
