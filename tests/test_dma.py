from backend.dma import scan_register_writes, match_staging, dma_observation_plan
from backend.core import CDL
from backend.server import app, session
from fastapi.testclient import TestClient


def test_dma_registers_absolute_and_long():
    rom=bytes([0x8D,0x0B,0x42,0x8F,0x18,0x21,0x00,0x8D,0x0C,0x42,0x8F,0x0B,0x42,0x7E])
    result=scan_register_writes(rom)
    assert [x['name'] for x in result['candidates']]==['MDMAEN','VMDATAL','HDMAEN']
    assert result['total']==3

def test_dma_cdl_filter():
    rom=bytes([0x8D,0x0B,0x42,0x8D,0x0C,0x42]);flags=bytes([1,0,0,0,0,0])
    d=CDL(flags,len(rom))
    r=scan_register_writes(rom,d,code_only=True)
    assert len(r['candidates'])==1 and r['candidates'][0]['name']=='MDMAEN'

def test_dma_bounds():
    import pytest
    with pytest.raises(ValueError):scan_register_writes(b'123',start=3)
    with pytest.raises(ValueError):scan_register_writes(b'123',length=100)

def test_wram_vram_staging():
    w=bytearray(0x20000);v=bytearray(0x10000)
    seq=bytes(range(32));w[0x10005:0x10025]=seq;v[:32]=seq
    r=match_staging(bytes(w),bytes(v),chunk_size=32,vram_length=32)
    assert any(x['wram_address']=='$7F:0005' for x in r['matches'])

def test_api_dma_plan_and_import():
    c=TestClient(app)
    assert c.get('/api/dma/plan').status_code==200
    assert c.get('/api/dma/registers').status_code==400 if session.rom is None else True
    assert c.get('/api/dma/staging?capture_id=unknown').status_code==400

def test_dma_plan_has_required_registers():
    data=dma_observation_plan()
    assert '$420B'==data['registers']['DMA enable']
