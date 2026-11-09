import pytest
from fastapi.testclient import TestClient
from backend.dma_trace import analyze_trace
from backend.server import app,session


def trace(rows):
    return ('cycle,pc,address,value,operation\n'+'\n'.join(rows)).encode()


def setup_trace(data_count=16):
    return trace([
        '0d1,$80:8000,$00:2115,80,write',
        '0d2,$80:8001,$00:2116,10,write',
        '0d3,$80:8002,$00:2117,00,write',
        '0d4,$80:8003,$00:4300,01,write',
        '0d5,$80:8004,$00:4301,18,write',
        '0d6,$80:8005,$00:4302,00,write',
        '0d7,$80:8006,$00:4303,20,write',
        '0d8,$80:8007,$00:4304,7E,write',
        f'0d9,$80:8008,$00:4305,{data_count:02X},write',
        '0d10,$80:8009,$00:4306,00,write',
        '0d11,$80:800A,$00:420B,01,write'
    ])


def test_dma_decode_and_exact_vram():
    ram=bytearray(131072);vram=bytearray(65536)
    ram[0x2000:0x2010]=bytes(range(16));vram[0x20:0x30]=bytes(range(16))
    r=analyze_trace(setup_trace(),wram=bytes(ram),vram=bytes(vram))
    assert r['dma_triggers']==1 and len(r['transfers'])==1
    x=r['transfers'][0]
    assert (x['source'],x['size'],x['vram_byte_address'])==(0x7e2000,16,32)
    assert x['verification']=='snapshot_exact_match'


def test_different_bytes_not_proven():
    r=analyze_trace(setup_trace(),wram=bytes(131072),vram=bytes([1]*65536))
    assert r['transfers'][0]['verification']=='snapshot_mismatch'


def test_unknown_configuration():
    r=analyze_trace(trace(['0d1,80:8000,00:420B,03,write']))
    assert len(r['transfers'])==2
    assert all(len(x['registers_missing'])>0 for x in r['transfers'])
    assert all(x['verification']=='not_checked' for x in r['transfers'])


def test_ignore_cpu_log():
    r=analyze_trace(b'80:A100 STA $420B\n80:A103 NOP\n')
    assert r['dma_triggers']==0 and r['meta']['format']=='cpu_trace_text'


def test_jsonl_and_read_are_not_writes():
    t=b'{"operation":"read","address":"00:420B","value":"01"}\n'+b'{"operation":"write","address":"00:420B","value":"01"}\n'
    r=analyze_trace(t)
    assert r['meta']['observed_writes']==1 and r['dma_triggers']==1


def test_wrapped_bank_not_io():
    r=analyze_trace(trace(['0d1,7E:8120,7E:420B,01,write']))
    assert r['dma_triggers']==0


def test_reject_invalid():
    with pytest.raises(ValueError):analyze_trace(trace(['0d1,80:8000,00:420B,100,write']))
    with pytest.raises(ValueError):analyze_trace(b'')


def test_api_import_and_analysis():
    c=TestClient(app)
    old=session.dma_trace
    try:
        response=c.post('/api/dma/trace',files={'file':('test.csv',setup_trace(),'text/csv')})
        assert response.status_code==200, response.text
        assert c.get('/api/dma/trace/status').json()['loaded']
        result=c.get('/api/dma/trace/analyze')
        assert result.status_code==200 and result.json()['dma_triggers']==1
    finally:
        session.dma_trace=old
