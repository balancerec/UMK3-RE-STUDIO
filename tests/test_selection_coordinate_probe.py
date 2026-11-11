"""Selection coordinate evidence checks; synthetic fixtures aren't Mesen traces."""
import pytest
from backend import selection_coordinate_probe as probe


def synthetic(monkeypatch):
    monkeypatch.setattr(probe, "verify", lambda data: None)
    rom=bytearray(0x800000)
    rom[0x47CF4D:0x47CF4D+len(probe.SIGNATURE)]=probe.SIGNATURE
    for i in range(29):
        rom[0x47B601+i*2:0x47B603+i*2]=(18+50*(i%7)).to_bytes(2,"little")
        rom[0x47B63B+i*2:0x47B63D+i*2]=((-157+54*(i//7))&65535).to_bytes(2,"little")
    return bytes(rom)


def test_reject_unknown_rom():
    with pytest.raises(ValueError,match="não autenticada"):
        probe.verify(b"not an authenticated game")


def test_decode_words_and_signed(monkeypatch):
    rom=synthetic(monkeypatch)
    slots=probe.coordinates(rom)["slots"]
    assert len(slots)==29
    assert (slots[0]["x_signed"],slots[0]["y_signed"])==(18,-157)
    assert slots[1]["x_signed"]==68


def test_signature_guard(monkeypatch):
    rom=bytearray(synthetic(monkeypatch))
    rom[0x47CF4D]=0xEA
    with pytest.raises(ValueError,match="assinatura"):
        probe.coordinates(bytes(rom))


def test_snapshot_values_do_not_imply_instruction(monkeypatch):
    rom=synthetic(monkeypatch)
    before=bytearray(probe.WRAM_SIZE)
    after=bytearray(before)
    after[probe.X_BASE:probe.X_BASE+2]=(18).to_bytes(2,"little")
    after[probe.Y_BASE:probe.Y_BASE+2]=((-157)&65535).to_bytes(2,"little")
    report=probe.compare_snapshots(rom,bytes(before),bytes(after),slot=0,x_register=0)
    assert report["both_match"]
    assert report["values"]["x"]["changed"]
    assert report["confidence"].startswith("CORRELAÇÃO")


def test_bad_snapshot_and_params(monkeypatch):
    rom=synthetic(monkeypatch)
    ram=bytes(probe.WRAM_SIZE)
    with pytest.raises(ValueError,match="131072"):
        probe.compare_snapshots(rom,b"a",b"b",slot=0,x_register=0)
    with pytest.raises(ValueError,match="Slot"):
        probe.compare_snapshots(rom,ram,ram,slot=29,x_register=0)
    with pytest.raises(ValueError,match="faixa"):
        probe.compare_snapshots(rom,ram,ram,slot=0,x_register=0x10000)
