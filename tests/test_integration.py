from pathlib import Path
from fastapi.testclient import TestClient
from backend.server import app,session
from backend.core import Rom,CDL,disassemble,control_flow

client=TestClient(app)

def test_status_and_home():
    assert client.get('/').status_code==200
    assert client.get('/api/status').status_code==200
    assert client.get('/api/disasm').status_code==400

def test_real_rom_if_available():
    paths=list(Path('/mnt/data').glob('*SnesPrgRom.dmp'))
    if not paths:return
    session.rom=Rom(paths[0].read_bytes())
    meta=client.get('/api/status').json()['rom']
    assert meta['mapping']=='exhirom' and meta['checksum']=='DE7A' and meta['checksum_calculated']=='DE7A'
    d=client.get('/api/disasm?offset=566588&count=1').json()
    assert d[0]['mnemonic']=='JML' and d[0]['target']==0xd05e62
    assert client.get('/api/translate?cpu=C8:A53C').json()['offset']==0x08a53c
    banks=client.get('/api/banks').json();assert len(banks)==128
    cdlpath=next(Path('/mnt/data').glob('*.cdl'),None)
    if cdlpath:
        session.cdl=CDL(cdlpath.read_bytes(),len(session.rom.data))
        assert session.cdl.stats()['code']==53748
    g=client.get('/api/graph?offset=566588&max_blocks=2').json()
    assert len(g['nodes'])>=1
    session.rom=None;session.cdl=None
