from io import BytesIO
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from PIL import Image
import pytest
from backend.extraction import bank_inventory, match_vram_windows, raw_entropy, run_candidates, preview_raw
from backend.storage import Store


def test_entropy_inventory_and_runs():
    data=bytes([0])*128+bytes(range(128))
    assert raw_entropy(bytes([0])*100)==0
    stats=bank_inventory(data,bank_size=128)
    assert len(stats)==2 and stats[0]['zero_percent']==100
    assert stats[0]['entropy']==0
    assert stats[1]['entropy']==7
    assert run_candidates(data,start=0,length=256,min_run=64)[0]['length']==129


def test_exact_search_finds_known_pattern_and_ignores_low_complexity():
    from backend.extraction import search_exact
    window=bytes(range(64))
    rom=b'\xaa'*64+window+b'\xbb'*64+window
    vram=window+b'\x00'*64
    scan=match_vram_windows(rom,vram,chunk_size=64,vram_length=128,minimum_unique=12)
    assert [x['rom_offset'] for x in scan['matches']]==[64,192]
    assert scan['statistics']['skipped_low_diversity']==1
    assert search_exact(rom,b'\xff')==[]
    assert match_vram_windows(rom,bytes([0])*64,chunk_size=64,minimum_unique=12)['matches']==[]


def test_invalid_inputs_and_raw_preview():
    with pytest.raises(ValueError):match_vram_windows(b'',b'a'*64,chunk_size=24)
    with pytest.raises(ValueError):match_vram_windows(b'',b'a'*64,step=0)
    with pytest.raises(ValueError):run_candidates(b'abc',start=3,length=1)
    tile=bytearray(32);tile[0]=0x80
    pic=preview_raw(bytes(tile),offset=0,bpp=4,columns=1,rows=1, palette=0,scale=2)
    assert pic.size==(16,16)
    with pytest.raises(ValueError):preview_raw(bytes(tile),offset=0,bpp=4,columns=2,rows=2,palette=0)


def test_api_scans_and_preview(monkeypatch):
    import backend.server as s
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(s,'store',Store(d));monkeypatch.setattr(s,'session',s.Session())
        cli=TestClient(s.app)
        rom=bytearray(0x10000);rom[0x1000:0x1040]=bytes(range(64))
        assert cli.post('/api/rom',files={'file':('test.sfc',bytes(rom))}).status_code==200
        vram=bytearray(65536);vram[:64]=bytes(range(64))
        assert cli.post('/api/graphics/vram',files={'file':('v.dmp',bytes(vram))}).status_code==200
        r=cli.get('/api/extract/match',params={'chunk_size':64,'vram_length':64})
        assert r.status_code==200 and r.json()['matches'][0]['rom_offset']==0x1000
        p=cli.get('/api/extract/preview.png',params={'offset':0,'bpp':4,'columns':1,'rows':1})
        assert p.status_code==200 and Image.open(BytesIO(p.content)).size==(16,16)
        assert len(cli.get('/api/extract/banks').json()['banks'])==1
        assert cli.get('/api/extract/runs',params={'length':65536}).status_code==200
        assert cli.get('/api/extract/match',params={'chunk_size':11}).status_code==422
        assert cli.get('/api/extract/preview.png',params={'offset':65535}).status_code==422


def test_real_rom_readonly_if_available():
    src=next(Path('/mnt/data').glob('*SnesPrgRom.dmp'),None)
    if not src:return
    data=src.read_bytes()
    assert len(data)==8*1024*1024
    banks=bank_inventory(data)
    assert len(banks)==128
    assert any(b['zero_percent']>90 for b in banks)
