from tools.dragon_slot_report import parse_ips, ips_impact, to_markdown


def ips(*recs):
    out = b'PATCH'
    for off, p in recs:
        out += off.to_bytes(3, 'big') + len(p).to_bytes(2, 'big') + p
    return out + b'EOF'


def test_parse_and_rle():
    blob = b'PATCH' + (5).to_bytes(3, 'big') + b'\x00\x00' + (4).to_bytes(2, 'big') + b'\x7f' + b'EOF'
    assert parse_ips(blob) == [(5, b'\x7f' * 4)]


def test_impact_counts_only_real_changes_in_regions():
    rom = bytes(0x400000)
    res = ips_impact(rom, ips((0x06A73B, b'\xff'), (0x06A73C, b'\x00'), (0x100, b'\x01')))
    reg = {r['region']: r for r in res['regions']}
    assert reg['despacho_cursor']['changed_bytes'] == 1          # byte igual (00 -> 00) não conta
    assert reg['despacho_cursor']['changes'][0] == {'offset': '0x06A73B', 'old': '00', 'new': 'FF'}
    assert reg['rodizio_ocultos']['changed_bytes'] == 0 and res['beyond_rom_end'] == 0


def test_impact_flags_expansion_records():
    res = ips_impact(bytes(0x10), ips((0x20, b'\x01')))
    assert res['beyond_rom_end'] == 1


def test_markdown_renders_minimal():
    a = {'dispatch': {'found': True, 'redirects': {}}, 'state_1c57': {'facts': []}, 'portrait': {'facts': []}, 'cycle': {'facts': []}}
    assert 'Slot 0x0A' in to_markdown(a)
