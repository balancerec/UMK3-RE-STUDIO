"""Bounded, version-aware comparisons; no guesses about unlock flags."""
import hashlib
import json

import pytest

from backend.roster_capture import MEMORY_SIZES, compare, details, read_dump, report


def test_known_watch_addresses_are_little_endian():
    data = bytearray(MEMORY_SIZES["wram"])
    data[0x1C59] = 0x1B
    data[0x36D0:0x36D2] = bytes.fromhex("1B 00")
    data[0x3A50:0x3A52] = bytes.fromhex("0A 00")
    got = details(bytes(data), "wram")["fields"]
    assert got["special_fallback_7e1c59"]["value"] == "1B"
    assert got["resolved_candidate_7e36d0"]["value"] == "001B"
    assert got["p1_roster_index_candidate_7e3a50"]["value"] == "000A"
    assert got["p1_roster_index_candidate_7e3a50"]["interpretation"] == "candidate_not_proven"


def test_binary_and_hex_accept_exact_lengths(tmp_path):
    raw = bytes([0xA5]) * MEMORY_SIZES["cgram"]
    binary = tmp_path / "cgram.bin"
    binary.write_bytes(raw)
    textual = tmp_path / "cgram.txt"
    textual.write_text("\n".join(" ".join(f"{x:02X}" for x in raw[i:i + 16])
                                 for i in range(0, len(raw), 16)), encoding="ascii")
    assert read_dump(binary, "cgram") == raw
    assert read_dump(textual, "cgram") == raw
    assert read_dump(textual, "cgram") == read_dump(binary, "cgram")


def test_rejects_truncated_and_decorated_dumps(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_text("00 01 02")
    with pytest.raises(ValueError, match="deve ter"):
        read_dump(path, "wram")
    path.write_text("00000: 00 01")
    with pytest.raises(ValueError, match="sem offsets"):
        read_dump(path, "cgram")


def test_reports_real_changed_fields_without_character_inference(tmp_path):
    a = bytearray(MEMORY_SIZES["wram"])
    b = bytearray(a)
    b[0x3A50] = 10
    b[0x52C8] = 27
    b[0x12000:0x12003] = b"ABC"
    pa = tmp_path / "a.wram"
    pb = tmp_path / "b.wram"
    pa.write_bytes(a)
    pb.write_bytes(b)
    sha = hashlib.sha256(bytes.fromhex("CA FE")).hexdigest()
    result = report(pa, pb, "wram", version_a="2.2", version_b="2.3",
                    rom_sha_a=sha, label_a="Shao Kahn", label_b="Jax")
    assert result["a"]["rom_sha256_claimed"] == sha
    assert result["comparison"]["changed_bytes"] == 5
    assert result["comparison"]["changed_by_region"] == {"7E": 2, "7F": 3}
    assert set(x["field"] for x in result["comparison"]["watched_fields_changed"]) == {
        "p1_roster_index_candidate_7e3a50", "stored_character_candidate_7e52c8"
    }
    assert result["observed_execution"] is False
    assert "identidade" in result["limitations"][2]


def test_limits_output_ranges_but_not_change_counts():
    a = bytes(MEMORY_SIZES["cgram"])
    b = bytearray(a)
    for i in range(0, 40, 2):
        b[i] = 0xFF
    got = compare(a, bytes(b), "cgram", max_ranges=3)
    assert got["changed_bytes"] == 20
    assert len(got["ranges"]) == 3
    assert got["ranges_truncated"] is True


def test_same_snapshot_has_zero_differences():
    a = bytes(MEMORY_SIZES["oam"])
    got = compare(a, a, "oam")
    assert got["changed_bytes"] == 0
    assert got["ranges"] == []
    assert got["ranges_truncated"] is False


def test_sha_is_validated(tmp_path):
    a = tmp_path / "a.cgram"
    a.write_bytes(bytes(MEMORY_SIZES["cgram"]))
    with pytest.raises(ValueError, match="64"):
        report(a, a, "cgram", version_a="2.2", version_b="2.3", rom_sha_b="invalid")
