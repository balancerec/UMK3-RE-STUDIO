import os, hashlib
import pytest
from backend.core import Rom, cpu_to_file
from backend import hidden_roster as hr

# Bytes extraídos da ROM real (ver docs/EVIDENCIAS.md, E-010 a E-014).
IDS = bytes.fromhex('18 13 05 02 03 10 17 01 00 11 FF 15 04 09 07 0F 14 12 08 0A 06 0E 0D 0C')
NAV = {
    'up': '00 01 02 03 04 05 06 00 01 02 03 04 05 06 08 09 0A 0B 0C 0E 0F 10 11 12',
    'down': '07 08 09 0A 0B 0C 0D 07 0E 0F 10 11 12 0D 13 14 15 16 17 13 14 15 16 17',
    'left': '00 00 01 02 03 04 05 07 07 08 09 0A 0B 0C 0E 0E 0F 10 11 13 13 14 15 16',
    'right': '01 02 03 04 05 06 06 08 09 0A 0B 0C 0D 0D 0F 10 11 12 12 14 15 16 17 0D',
}


def synthetic_rom():
    raw = bytearray(0x80000)
    o = cpu_to_file(hr.ID_TABLE_CPU); raw[o:o + 24] = IDS
    for k, (cpu, _) in hr.NAV_TABLES.items():
        o = cpu_to_file(cpu); raw[o:o + 24] = bytes.fromhex(NAV[k])
    rom = Rom(bytes(raw)); rom.mapping = 'exhirom'
    return rom


def test_resolution_matches_observed_cases():
    t = hr.read_tables(synthetic_rom())
    assert hr.resolve_character(0x03, t['ids'], 0) == 0x02          # Jax: índice 3 -> ID 2
    assert hr.resolve_character(0x0A, t['ids'], 0x1A) == 0x1A      # oculto + Motaro
    assert hr.resolve_character(0x0A, t['ids'], 0x19) == 0x19      # oculto + Idels
    assert hr.resolve_character(0x0A, t['ids'], 0x0B) == 0x0B      # oculto + Sheeva


def test_hidden_ids_absent_from_visible_table():
    visible = set(IDS) - {0xFF}
    assert {0x0B, 0x16, 0x19, 0x1A, 0x1B}.isdisjoint(visible)


def test_navigation_grid_is_consistent():
    nav = {k: bytes.fromhex(v) for k, v in NAV.items()}
    assert hr.navigate(0x10, 0x0800, nav) == 0x0A                   # linha 3, coluna central -> sobe ao slot oculto
    assert all(len(v) == 24 and max(v) < 24 for v in nav.values())
    assert [len(r) for r in hr.grid_rows(IDS)] == [7, 7, 5, 5]
    assert hr.grid_rows(IDS)[1][3] == 0xFF                          # slot oculto no centro da linha 2


def test_scan_finds_sta_1c59():
    data = bytearray(64); data[10:14] = bytes([0x8D, 0x59, 0x1C, 0xEA])
    r = hr.scan_wram_writes(bytes(data), 0x1C59, 'hirom')
    assert len(r) == 1 and r[0]['offset'] == 10 and r[0]['kind'] == 'STA abs'


@pytest.mark.skipif(not os.environ.get('UMK3_ROM'), reason='defina UMK3_ROM=caminho da ROM local')
def test_real_rom_tables():
    raw = open(os.environ['UMK3_ROM'], 'rb').read()
    assert hashlib.sha256(raw).hexdigest() == hr.ROM_SHA256
    rom = Rom(raw); t = hr.read_tables(rom)
    assert t['ids'] == IDS
    for k in NAV: assert t['nav'][k] == bytes.fromhex(NAV[k])
