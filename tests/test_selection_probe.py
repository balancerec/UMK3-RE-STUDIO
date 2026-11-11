"""Dados sintéticos: os testes não constituem evidência da ROM."""
from types import SimpleNamespace
from backend.selection_probe import analyze_lines, analyze_trace

def line(seq, pc, mnemonic, ea=None, before=None, a=None, m=False, basis="trace"):
    return SimpleNamespace(
        seq=seq, cpu="65C816", pc=pc, mnemonic=mnemonic,
        ea=ea, ea_basis=basis if ea is not None else None,
        mem_value=before, flags={"m": m} if m is not None else {},
        regs={} if a is None else {"A": a}, text=mnemonic,
    )

def test_two_navigation_paths():
    events = [
        line(1, 0x86A73F, "lda", 0x7E1C57, 0),
        line(2, 0x86A76A, "sta", 0x7E0C0E, 10, 3),
        line(3, 0x86A7A8, "sta", 0x7E3A50, 10, 3),
        line(4, 0x86A77A, "sta", 0x7E0C0E, 10, 16),
        line(5, 0x86A7A8, "sta", 0x7E3A50, 3, 16),
    ]
    report = analyze_lines(events)
    assert report["cursor_destinations_derived"] == {"0003": 1, "0010": 1}
    assert report["observed_state_values"] == ["0000"]
    assert report["cursor_writes"][0]["confidence"] == "DERIVADO"

def test_missing_ea_never_claims_cursor_write():
    report = analyze_lines([line(1, 0x86A7A8, "sta", a=10)])
    assert report["cursor_writes"] == []
    assert report["observations"][0]["confidence"] == "NÃO VERIFICADO"

def test_8bit_and_unknown_width():
    report = analyze_lines([
        line(1, 0x86A7A8, "sta", 0x7E3A50, a=0x1234, m=True),
        line(2, 0x86A7A8, "sta", 0x7E3A50, a=0x1234, m=None),
    ])
    assert report["cursor_writes"][0]["written_derived"] == "0034"
    assert report["cursor_writes"][1]["written_derived"] is None

def test_unconfirmed_address_basis():
    report = analyze_lines([
        line(1, 0x86A7A8, "sta", 0x7E3A50, a=10, basis="calculado")
    ])
    assert report["cursor_writes"][0]["confidence"] == "NÃO VERIFICADO"

def test_trace_parser_integration():
    raw = (b"86A7A8 sta ($94) [$7E3A50] = $0003 "
           b"A:0010 X:0000 Y:0000 S:01FF D:0C00 DB:7E P:nvmxdIzc\n")
    report = analyze_trace(raw)
    assert report["cursor_destinations_derived"] == {"0010": 1}
    assert report["cursor_writes"][0]["confidence"] == "DERIVADO"
