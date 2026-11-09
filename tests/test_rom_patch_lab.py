"""Tests for standalone ROM Patch Lab. No copyrighted ROM needed."""
import hashlib
import json

import pytest

from tools.rom_patch_lab import apply_ips, compare_roms, make_ips, main


def rom():
    return bytearray(0x10000)


def test_no_changes_roundtrip():
    base = bytes(rom())
    result = compare_roms(base, base)
    assert result["identical"]
    assert result["changed_bytes"] == 0
    assert apply_ips(base, make_ips(base, base)) == base


def test_disjoint_changes_and_report():
    before = bytes(rom())
    after = rom()
    after[0x201:0x205] = b"UMK3"
    after[0x901] = 0x8A
    result = compare_roms(before, bytes(after))
    assert result["changed_bytes"] == 5
    assert result["regions_total"] == 2
    assert result["regions_in_report"][0]["offset"] == "0x000201"
    assert apply_ips(before, make_ips(before, bytes(after))) == bytes(after)


def test_splits_long_runs_at_ips_record_limit():
    base = bytes(rom())
    changed = bytes([0x5A]) * len(base)
    assert apply_ips(base, make_ips(base, changed)) == changed


def test_reject_size_difference():
    with pytest.raises(ValueError, match="mesmo tamanho"):
        compare_roms(bytes(rom()), bytes(rom()) + b"X")


def test_reject_truncated_or_out_of_bounds_ips():
    base = bytes(rom())
    for patch in (b"", b"PATCH", b"PATCH\x00\x00\x01\x00\x02A", b"PATCH\x00\xFF\xFF\x00\x02ABEOF"):
        with pytest.raises(ValueError):
            apply_ips(base, patch)


def test_rle_ips_read_support():
    base = bytes(rom())
    patch = b"PATCH" + (32).to_bytes(3, "big") + b"\x00\x00\x00\x03" + b"Z" + b"EOF"
    result = apply_ips(base, patch)
    assert result[32:35] == b"ZZZ"


def test_cli_diff_verify_inspect(tmp_path, capsys):
    before = tmp_path / "original.sfc"
    modified = tmp_path / "modified.sfc"
    patch = tmp_path / "change.ips"
    report = tmp_path / "change.json"
    before.write_bytes(bytes(rom()))
    updated = rom()
    updated[123:126] = b"MKR"
    modified.write_bytes(updated)
    assert main(["inspect", str(before)]) == 0
    assert main(["diff", str(before), str(modified), "--ips", str(patch), "--report", str(report)]) == 0
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["changed_bytes"] == 3
    assert saved["modified_sha256"] == hashlib.sha256(updated).hexdigest()
    assert main(["verify", str(before), str(patch), "--expected-sha256", saved["modified_sha256"]]) == 0
    assert "match" in capsys.readouterr().out
    with pytest.raises(SystemExit) as exc:
        main(["diff", str(before), str(modified), "--ips", str(patch)])
    assert exc.value.code == 2


def test_ips_reserved_eof_record_offset():
    # IPS cannot place a record header at 0x454F46, but must still
    # encode modifications at that ROM offset.
    original = bytes(0x800000)
    changed = bytearray(original)
    changed[0x454F46] = 0x77
    result = apply_ips(original, make_ips(original, bytes(changed)))
    assert result == bytes(changed)


def test_ips_crosses_reserved_eof_boundary():
    original = bytes(0x800000)
    changed = bytearray(original)
    changed[0x454F45:0x454F48] = b"ABC"
    assert apply_ips(original, make_ips(original, bytes(changed))) == bytes(changed)
