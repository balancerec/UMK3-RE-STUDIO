import pytest
from fastapi.testclient import TestClient
from backend.core import Rom
from backend.correlation import correlate_trace
from backend.server import app, session


def trace(rows):
    return ('cycle,pc,address,value,operation\n'+'\n'.join(rows)).encode()


def sample():
    return trace([
        '0d1,C8:A53C,00:2115,80,write',
        '0d2,C8:A53C,00:2116,10,write',
        '0d3,C8:A53C,00:2117,00,write',
        '0d4,C8:A53C,00:4300,01,write',
        '0d5,C8:A53C,00:4301,18,write',
        '0d6,C8:A53C,00:4302,00,write',
        '0d7,C8:A53C,00:4303,20,write',
        '0d8,C8:A53C,00:4304,7E,write',
        '0d9,C8:A53C,00:4305,10,write',
        '0d10,C8:A53C,00:4306,00,write',
        '0d11,C8:A53C,00:420B,01,write'])


def test_provenance_rom_pc_and_caution():
    data=bytearray(0x800000)
    data[0x08a53c:0x08a540]=bytes.fromhex('5c625ed0')
    rom=Rom(bytes(data))
    # Detection on synthetic zero ROM isn't authoritative; force known mapping.
    rom.mapping='exhirom'
    out=correlate_trace(sample(),rom=rom,wram=bytes(131072),vram=bytes(65536))
    assert out['dma_triggers']==1
    entry=out['transfers'][0]
    assert entry['trigger']['rom_offset']==0x08a53c
    assert entry['trigger']['instruction']['mnemonic']=='JML'
    assert entry['source_kind']=='WRAM'
    assert any('não identificada' in w for w in entry['warnings'])
    assert entry['classification']=='observed_trigger_inferred_transfer'


def test_no_trace_does_not_invent_activity():
    r=correlate_trace(b'80:A53C STA $420B\n')
    assert r['transfers']==[] and r['dma_triggers']==0


def test_unmapped_pc_and_incomplete():
    r=correlate_trace(trace(['0d1,7E:8000,00:420B,01,write']))
    assert r['transfers'][0]['trigger']['rom_offset'] is None
    assert 'Configuração DMA incompleta' in r['transfers'][0]['warnings']


def test_limits():
    with pytest.raises(ValueError):correlate_trace(sample(),max_results=501)


def test_api_requires_imported_trace():
    client=TestClient(app)
    original=session.dma_trace
    try:
        session.dma_trace=None
        response=client.get('/api/correlation/analyze')
        assert response.status_code==400
        session.dma_trace=sample()
        response=client.get('/api/correlation/analyze')
        assert response.status_code==200 and response.json()['dma_triggers']==1
    finally:session.dma_trace=original
