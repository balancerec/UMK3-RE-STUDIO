"""Regression tests for audit fixes in v1.0.1."""
import tempfile
from backend.core import CpuState, Rom, decode_one, disassemble, next_instruction_offset
from backend.analysis import build_xrefs
from backend.storage import Store
from fastapi.testclient import TestClient

def test_65c816_pc_wrap_with_operand():
    raw=bytearray(0x20000)
    raw[0xFFFF]=0x5C
    raw[0:3]=bytes([0x12,0x34,0xC0])
    raw[0x10000]=0xEA
    rom=Rom(bytes(raw));rom.mapping="hirom"
    ins=decode_one(rom.data,0xFFFF,CpuState(),rom.mapping)
    assert ins["bytes"]=="5C 12 34 C0" and ins["target"]==0xC03412
    assert next_instruction_offset(0xFFFF,1,"hirom")==0

def test_sequential_and_xref_wrap():
    raw=bytearray(0x20000)
    raw[0xFFFF]=0xEA
    raw[0]=0x22
    raw[1:4]=bytes([0x10,0x00,0xC0])
    raw[4]=0x6B
    raw[0x10]=0x6B
    rom=Rom(bytes(raw));rom.mapping="hirom"
    decoded=disassemble(rom,0xFFFF,2)
    assert [x["offset"] for x in decoded]==[0xFFFF,0]
    refs=build_xrefs(rom,[0xFFFF],max_instructions=40)["references"]
    assert any(r["from_offset"]==0 and r["to_offset"]==0x10 for r in refs)

def test_plp_and_rti_do_not_change_e():
    for opname in ("PLP","RTI"):
        s=CpuState(e=True,m=True,x=True)
        s.update(opname,None)
        assert (s.e,s.m,s.x)==(True,True,True)

def test_dma_trace_persistence_and_reopen():
    with tempfile.TemporaryDirectory() as tmp:
        s=Store(tmp);p=s.create("DMA")
        raw=b"cycle,pc,address,value,operation\n0d1,,$00420B,$01,write\n"
        sha=s.save_graphics_asset(p["id"],"dma_trace",raw,"events.csv")
        reopened=Store(tmp)
        assert reopened.graphics_assets(p["id"])["dma_trace"]==sha
        assert reopened.load_artifact(sha)==raw

def test_dma_api_upload_convert_and_reopen(monkeypatch):
    import backend.server as srv
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(srv,"store",Store(tmp))
        monkeypatch.setattr(srv,"session",srv.Session())
        c=TestClient(srv.app)
        pid=c.post("/api/projects",json={"name":"DMA"}).json()["id"]
        raw=b"cycle,pc,address,value,operation\n0d1,,$00420B,$01,write\n"
        r=c.post("/api/dma/trace",files={"file":("trace.csv",raw)})
        assert r.status_code==200,r.text
        r=c.post("/api/capture/convert",files={"file":("log.txt",b"UMK3_DMA,0d1,$C08A10,$00420B,$01,write\n")})
        assert r.status_code==200,r.text
        assert "$C08A10" in r.json()["csv"]
        assert c.post(f"/api/projects/{pid}/open").status_code==200
        assert c.get("/api/dma/trace/status").json()["loaded"]

def test_export_mlb_includes_symbols_beyond_preview_limit(monkeypatch):
    import backend.server as srv
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(srv,"store",Store(tmp))
        monkeypatch.setattr(srv,"session",srv.Session())
        c=TestClient(srv.app)
        pid=c.post("/api/projects",json={"name":"symbols"}).json()["id"]
        for i in range(2003):
            srv.store.add_symbol(pid,"SnesPrgRom",i,f"Sym{i}")
        c.post(f"/api/projects/{pid}/open")
        data=c.get("/api/mlb/export")
        assert data.status_code==200
        assert "Sym2002" in data.text
        assert len(data.text.splitlines())==2003
