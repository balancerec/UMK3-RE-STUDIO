import pytest
from backend.capture import convert_capture,capture_audit,capture_plan
from fastapi.testclient import TestClient
from backend.server import app

def raw_log():
    return b'''[INFO] script started\nUMK3_DMA,0d1,,$004300,$01,write\nUMK3_DMA,0d2,,$004301,$18,write\nUMK3_DMA,0d3,,$004302,$00,write\nUMK3_DMA,0d4,,$004303,$20,write\nUMK3_DMA,0d5,,$004304,$7E,write\nUMK3_DMA,0d6,,$004305,$10,write\nUMK3_DMA,0d7,,$004306,$00,write\nUMK3_DMA,0d8,,$002115,$80,write\nUMK3_DMA,0d9,,$002116,$00,write\nUMK3_DMA,0d10,,$002117,$00,write\nUMK3_DMA,0d11,,$00420B,$01,write\n'''

def test_convert_and_audit():
    csv=convert_capture(raw_log())
    assert csv.startswith(b'cycle,pc,address,value,operation')
    audit=capture_audit(csv)
    assert audit['observed_events']==11
    assert audit['dma_triggers']==1
    assert audit['candidate_transfers']==1
    assert not audit['issues']

def test_incomplete_warning():
    raw=b'UMK3_DMA,0d1,,$00420B,$01,write\n'
    audit=capture_audit(convert_capture(raw))
    assert audit['issues']

def test_reject_bad_records():
    with pytest.raises(ValueError):convert_capture(b'no logging at all')
    with pytest.raises(ValueError):convert_capture(b'UMK3_DMA,5,,$00420B,$01,write')
    with pytest.raises(ValueError):convert_capture(b'UMK3_DMA,0d1,,$00420B,$AA,read')

def test_plan_and_api():
    client=TestClient(app)
    assert client.get('/api/capture/plan').status_code==200
    assert len(capture_plan()['targets'])==3
    assert client.get('/api/capture/script.lua').status_code==200
    result=client.post('/api/capture/convert',files={'file':('example.txt',raw_log(),'text/plain')})
    assert result.status_code==200, result.text
    assert result.json()['audit']['dma_triggers']==1
    assert client.get('/api/capture/audit').status_code==200

def test_reject_normal_cpu_trace():
    with pytest.raises(ValueError):convert_capture(b'PC C0:1234 STA $420B\n')
