"""Decompression hypothesis lab tests; no UMK3 proprietary codec is asserted."""
import pytest
from backend.decompression import decode_stream,compare_pair,scan_hypotheses,region_profile

def test_raw_and_rle():
    assert decode_stream(b"abc","raw",3).data==b"abc"
    assert decode_stream(bytes([3,65,2,66]),"rle_count_value",5).data==b"AAABB"
    assert decode_stream(bytes([65,3,66,2]),"rle_value_count",5).data==b"AAABB"

def test_packbits():
    d=decode_stream(bytes([0x80,2,65,66,67,0xFE,90]),"packbits",6)
    assert d.complete and d.data==b"ABCZZZ"

def test_malformed_inputs():
    assert not decode_stream(bytes([0,65]),"rle_count_value",3).complete
    assert not decode_stream(bytes([4,65]),"rle_count_value",3).complete
    with pytest.raises(ValueError):decode_stream(b"abc","unknown_umk3",2)

def test_pair_exact_is_not_codec_confirmation():
    rom=b"_"*8+bytes([3,65,2,66])
    r=compare_pair(rom,b"AAABB",8,0,5,"rle_count_value")
    assert r["exact_match"] and r["classification"]=="exact_match_for_one_window_only"

def test_scan_and_region_profile():
    rom=bytes([4,65,4,66])+bytes(256)
    target=b"AAAABBBB"
    r=scan_hypotheses(rom,target,0,16,0,8,1,("rle_count_value",))
    assert r["matches_exact"]>=1
    assert region_profile(bytes([0])*256,0,256,256)["windows"][0]["entropy"]==0

def test_http_api_requires_imports():
    from backend.server import app,session
    from fastapi.testclient import TestClient
    before=(session.rom,dict(session.graphics))
    try:
        session.rom=None;session.graphics.clear()
        c=TestClient(app)
        assert c.post("/api/research/pair",json={"rom_offset":0,"target_offset":0,"length":8}).status_code==400
    finally:
        session.rom,session.graphics=before
