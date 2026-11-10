"""Regression: native-mode reset and static code traversal on 65C816."""
from backend.core import CpuState, Rom, decode_one
from backend.analysis import build_xrefs


def test_clc_xce_rep_resolves_native_16bit_immediate():
    program = bytes.fromhex("18 FB C2 30 A9 34 12")
    state = CpuState(e=True, m=True, x=True)
    offsets = [0, 1, 2, 4]
    decoded = []
    for address in offsets:
        ins = decode_one(program, address, state, "hirom")
        decoded.append(ins)
        assert ins["size"] is not None
        state = CpuState(**ins["state_after"])
    assert [x["mnemonic"] for x in decoded] == ["CLC", "XCE", "REP", "LDA"]
    assert [x["size"] for x in decoded] == [1, 1, 2, 3]
    assert (state.e, state.m, state.x) == (False, False, False)
    assert state.c is True  # E was set at reset and moved into C by XCE.


def test_unknown_carry_stays_unknown_after_xce():
    state = CpuState(e=True, m=True, x=True)
    state.update("XCE", None)
    assert state.e is None
    assert state.m is None
    assert state.x is None


def test_sec_xce_retains_emulation_width():
    state = CpuState(e=False, m=False, x=False)
    state.update("SEC", None)
    state.update("XCE", None)
    assert (state.e, state.m, state.x, state.c) == (True, True, True, False)


def test_reset_flow_explores_jml_after_rep():
    data = bytearray([0xFF] * 65536)
    data[0xFFC0:0xFFD5] = b"BOOTSTRAP TEST".ljust(21, b" ")
    data[0xFFD5] = 0x21
    data[0xFFDC:0xFFE0] = b"\xff\xff\x00\x00"
    data[0xFFFC:0xFFFE] = b"\x00\x80"
    data[0x8000:0x800C] = bytes.fromhex("78 D8 18 FB C2 30 A9 34 12 5C 00 81")
    data[0x800C] = 0xC0  # destination is $C0:8100
    data[0x8100] = 0x6B  # RTL
    rom = Rom(bytes(data))
    assert rom.mapping == "hirom"
    report = build_xrefs(rom, [0x8000], initial_state=CpuState(True, True, True), max_instructions=60)
    assert report["instructions"] >= 7, report
    assert report["references"][0]["to_cpu"] == 0xC08100
    assert report["references"][0]["to_offset"] == 0x8100
    assert not report["ambiguous"]
