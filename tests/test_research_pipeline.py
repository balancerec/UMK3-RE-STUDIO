"""Testes sintéticos; não comprovam comportamento da ROM comercial."""
import pytest

from backend import research_pipeline as rp


def mock_rom(monkeypatch):
    # Desabilita a autenticação SOMENTE na fixture sintética.
    monkeypatch.setattr(rp, "require_arcade", lambda data: {"authenticated": True})
    data = bytearray(0x800000)
    # Cada destino avança um slot: todos os slots são alcançáveis.
    data[0x47B570:0x47B570+29] = bytes(range(29))
    for cpu in rp.NAV_CPU.values():
        data[cpu:cpu+29] = bytes((i+1) % 29 for i in range(29))
    return data


def test_reject_unknown_rom():
    bad = bytes(0x800000)
    assert rp.authenticate(bad)["authenticated"] is False
    with pytest.raises(ValueError, match="não autenticada"):
        rp.extract_selection(bad)


def test_extract_tables_and_connectivity(monkeypatch):
    data = mock_rom(monkeypatch)
    report = rp.extract_selection(bytes(data))
    assert len(report["slots"]) == 29
    assert report["all_reachable"]
    assert report["slots"][28]["row"] == 4
    assert report["slots"][10]["navigation"]["up"] == 11
    assert report["slots"][0]["id"] == "00"


def test_reject_invalid_destination(monkeypatch):
    data = mock_rom(monkeypatch)
    data[0x47B58D] = 29
    with pytest.raises(ValueError, match="fora da grade"):
        rp.extract_selection(bytes(data))


def test_disassembly_uses_existing_decoder(monkeypatch):
    data = mock_rom(monkeypatch)
    # PHX PHY RTL : decoded without interpreting arbitrary data as execution.
    data[0x47CF4D:0x47CF50] = b"\xDA\x5A\x6B"
    report = rp.disassemble_window(bytes(data), 0x47CF4D)
    assert [x["mnemonic"] for x in report["instructions"]] == ["PHX", "PHY", "RTL"]
    with pytest.raises(ValueError):
        rp.disassemble_window(bytes(data), 0x401234)


def test_two_word_tables_are_explicitly_hypothetical(monkeypatch):
    data = mock_rom(monkeypatch)
    data[0x47B601:0x47B605] = b"\x34\x12\x78\x56"
    out = rp.examine_pair_candidates(bytes(data))
    assert out["tables"][0]["words_little_endian"][:2] == [0x1234, 0x5678]
    assert out["tables"][0]["meaning"] == "NÃO VERIFICADO"
    assert len(out["tables"][1]["words_little_endian"]) == 29


def test_compare_vram_and_palette():
    a = bytearray(0x10000)
    b = bytearray(a)
    b[0] = 0x80
    b[31] = 0x40
    result = rp.compare_graphics_snapshot(bytes(a), bytes(b), kind="vram")
    assert result["changed_bytes"] == 2
    assert result["changed_4bpp_tile_indices"] == [0]
    x = bytearray(512)
    y = bytearray(x)
    y[2] = 0x1f
    palette = rp.compare_graphics_snapshot(bytes(x), bytes(y), kind="cgram")
    assert [e["index"] for e in palette["changed_palette_entries"]] == [1]


def test_size_and_type_rejection():
    with pytest.raises(ValueError):
        rp.compare_graphics_snapshot(b"abc", b"abc", kind="vram")
    with pytest.raises(ValueError):
        rp.compare_graphics_snapshot(b"x", b"y", kind="rom")
