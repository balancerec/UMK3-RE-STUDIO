"""Read-only coordinate probe for authenticated UMK3 Arcade Edition beta 71.

Static ASM establishes LDA table[slot*2] and candidate STA $3DA8,X /
$3F18,X. WRAM snapshot matching is not proof of which instruction wrote it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from .core import cpu_to_file

MD5 = "b04388eef6071792d85f97dab46c471c"
SHA256 = "60b948a785ed86d927b02ce862c0f37dfbed09ba725ab57902dfd34d1c832d6e"
ROUTINE = 0x47CF4D
SIGNATURE = bytes.fromhex(
    "DA 5A B2 94 0A A8 A6 2A DA BB BF 3B B6 47 48 "
    "BF 01 B6 47 7A FA 9D A8 3D 98 9D 18 3F 7A FA 6B")
N = 29
WRAM_SIZE = 0x20000
X_BASE, Y_BASE = 0x3DA8, 0x3F18


def verify(data: bytes):
    if len(data) != 0x800000 or hashlib.md5(data).hexdigest() != MD5 or hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("ROM não autenticada: requer Arcade Edition beta 71 sem cabeçalho")


def region(data: bytes, cpu: int, size: int):
    ofs = cpu_to_file(cpu, "exhirom")
    if ofs is None or ofs < 0 or ofs + size > len(data):
        raise ValueError(f"Endereço de ROM inválido: {cpu:06X}")
    return data[ofs:ofs+size]


def coordinates(rom: bytes):
    verify(rom)
    if region(rom, ROUTINE, len(SIGNATURE)) != SIGNATURE:
        raise ValueError("A assinatura da rotina 47:CF4D diverge")
    a = region(rom, 0x47B601, 2*N)
    b = region(rom, 0x47B63B, 2*N)
    def signed(v):
        return v-65536 if v & 0x8000 else v
    records=[]
    for i in range(N):
        x=int.from_bytes(a[2*i:2*i+2], "little")
        y=int.from_bytes(b[2*i:2*i+2], "little")
        records.append({"slot": i, "x_raw": f"{x:04X}", "y_raw": f"{y:04X}",
                        "x_signed": signed(x), "y_signed": signed(y)})
    return {"md5": MD5, "sha256": SHA256, "routine": "47:CF4D",
            "evidence": "BYTES CONFIRMADOS; interpretação X/Y é fluxo estático",
            "x_table": "47:B601", "y_table": "47:B63B",
            "writes_if_dbr_is_wram": ["$3DA8,X", "$3F18,X"],
            "slots": records}


def compare_snapshots(rom: bytes, before: bytes, after: bytes, *, slot: int, x_register: int):
    if len(before) != WRAM_SIZE or len(after) != WRAM_SIZE:
        raise ValueError("Dumps devem conter 131072 bytes a partir de $7E:0000")
    if not 0 <= slot < N:
        raise ValueError("Slot inválido")
    if not 0 <= x_register <= 0xFFFE-Y_BASE:
        raise ValueError("X fora da faixa que permite palavras na mesma página de banco")
    rec = coordinates(rom)["slots"][slot]
    results={}
    for axis, base in (("x", X_BASE), ("y", Y_BASE)):
        offset=base+x_register
        first=int.from_bytes(before[offset:offset+2],"little")
        second=int.from_bytes(after[offset:offset+2],"little")
        expected=int(rec[axis+"_raw"],16)
        results[axis]={"address":f"7E:{offset:04X}", "before":f"{first:04X}",
                       "after":f"{second:04X}", "expected":f"{expected:04X}",
                       "matches":second==expected, "changed":first!=second}
    return {"slot":slot, "x_register":x_register, "values":results,
            "both_match":all(r["matches"] for r in results.values()),
            "confidence":"CORRELAÇÃO DE SNAPSHOT, NÃO PROVA DE ESCRITA",
            "warning":"Conferir DBR, D, X, M e instruções executadas no Mesen."}


def main(argv=None):
    p=argparse.ArgumentParser(description="Sonda somente leitura para coordenadas da seleção beta 71")
    p.add_argument("rom",type=Path)
    p.add_argument("--before",type=Path)
    p.add_argument("--after",type=Path)
    p.add_argument("--slot",type=int)
    p.add_argument("--x-register",type=lambda s:int(s,0),default=0)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    rom=a.rom.read_bytes()
    result={"coordinates":coordinates(rom)}
    if any(v is not None for v in (a.before,a.after,a.slot)):
        if a.before is None or a.after is None or a.slot is None:
            p.error("Use --before, --after e --slot juntos")
        result["snapshot"]=compare_snapshots(rom,a.before.read_bytes(),
                                              a.after.read_bytes(),slot=a.slot,
                                              x_register=a.x_register)
    content=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if a.out:
        with a.out.open("x",encoding="utf-8") as f:f.write(content)
    else:
        print(content,end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
