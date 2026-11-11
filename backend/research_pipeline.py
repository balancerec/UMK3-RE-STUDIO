"""UMK3 Arcade beta 71: research pipeline, read-only and evidence-ranked.

Only runs the known offsets after checking the *exact* authenticated ROM hash.
Never writes game bytes or claims that an arbitrary data pattern is executed code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .core import CpuState, cpu_to_file, decode_one, next_instruction_offset
from .graphics import validate_dump, decode_cgram, decode_tile

ARCADE_SHA256 = "60b948a785ed86d927b02ce862c0f37dfbed09ba725ab57902dfd34d1c832d6e"
ARCADE_MD5 = "b04388eef6071792d85f97dab46c471c"
ROM_BYTES = 0x800000
ID_CPU = 0x47B570
NAV_CPU = {"up": 0x47B58D, "down": 0x47B5AA,
           "left": 0x47B5C7, "right": 0x47B5E4}
PAIR_CANDIDATES = (0x47B601, 0x47B63B)
ROWS = (7, 7, 5, 5, 5)
COUNT = sum(ROWS)
NAMES = {
    0: "Kano", 1: "Sonya", 2: "Jax", 3: "Nightwolf",
    4: "Sub-Zero (sem mascara)", 5: "Stryker", 6: "Sindel",
    7: "Sektor", 8: "Cyrax", 9: "Kung Lao", 10: "Kabal",
    11: "Sheeva", 12: "Shang Tsung", 13: "Liu Kang",
    14: "Smoke (ciborgue)", 15: "Kitana", 16: "Jade",
    17: "Mileena", 18: "Scorpion", 19: "Reptile",
    20: "Ermac", 21: "Sub-Zero (classico)", 23: "Noob",
    24: "Rain", 25: "Chameleon (atribuicao da Arcade)",
    26: "Motaro", 27: "Shao Kahn", 28: "Khameleon", 255: "Aleatorio",
}
# IDs represent only a documented naming hypothesis until confirmed on Mesen.
ENTRY_POINTS = (0x86A1F6, 0x86A383, 0x86A73A, 0x86A7A6, 0x47CF4D)


def authenticate(data: bytes) -> dict:
    md5 = hashlib.md5(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()
    ok = len(data) == ROM_BYTES and md5 == ARCADE_MD5 and sha256 == ARCADE_SHA256
    return {"bytes": len(data), "md5": md5, "sha256": sha256,
            "version": "Arcade Edition beta 71" if ok else "unknown",
            "authenticated": ok}


def require_arcade(data: bytes):
    identity = authenticate(data)
    if not identity["authenticated"]:
        raise ValueError("ROM não autenticada como Arcade Edition beta 71: " +
                         json.dumps(identity, ensure_ascii=False))
    return identity


def read_cpu(data: bytes, cpu: int, size: int) -> bytes:
    if not 0 < size <= 1024:
        raise ValueError("Tamanho de leitura inválido")
    offset = cpu_to_file(cpu, "exhirom")
    if offset is None or offset + size > len(data):
        raise ValueError("Endereço de ROM inválido")
    return data[offset:offset + size]


def extract_selection(data: bytes) -> dict:
    identity = require_arcade(data)
    ids = read_cpu(data, ID_CPU, COUNT)
    nav = {name: read_cpu(data, cpu, COUNT) for name, cpu in NAV_CPU.items()}
    bad = {k: [{"slot": i, "destination": v}
               for i, v in enumerate(values) if v >= COUNT]
           for k, values in nav.items()}
    if any(bad.values()):
        raise ValueError("Tabela de navegação contém índices fora da grade")
    reachable = {}
    for origin in range(COUNT):
        seen, pending = {origin}, [origin]
        while pending:
            x = pending.pop()
            for table in nav.values():
                y = table[x]
                if y not in seen:
                    seen.add(y)
                    pending.append(y)
        reachable[str(origin)] = sorted(seen)
    slots = []
    for i, character_id in enumerate(ids):
        row = next(j for j, start in enumerate((0, 7, 14, 19, 24))
                   if start <= i < start + ROWS[j])
        slots.append({
            "slot": i, "row": row, "column": i - (0, 7, 14, 19, 24)[row],
            "id": f"{character_id:02X}",
            "name_candidate": NAMES.get(character_id, "NÃO VERIFICADO"),
            "name_confidence": "CORRELAÇÃO DOCUMENTAL (NÃO TRACE)",
            "navigation": {name: table[i] for name, table in nav.items()},
        })
    return {
        "source": identity, "evidence": "CONFIRMADO POR BYTES",
        "id_table": f"{ID_CPU:06X}", "navigation_tables":
            {k: f"{v:06X}" for k, v in NAV_CPU.items()},
        "rows": list(ROWS), "slots": slots,
        "all_reachable": all(len(s) == COUNT for s in reachable.values()),
        "reachable_counts": {i: len(s) for i, s in reachable.items()},
        "table_hex": {"ids": ids.hex(" "), **{k: v.hex(" ") for k, v in nav.items()}},
    }


def disassemble_window(data: bytes, entry_cpu: int, *, limit: int = 24,
                       m: bool = False, x: bool = False) -> dict:
    require_arcade(data)
    if entry_cpu not in ENTRY_POINTS:
        raise ValueError("Entrada não está na lista de checkpoints investigados")
    if not 1 <= limit <= 96:
        raise ValueError("Limite inválido")
    offset = cpu_to_file(entry_cpu, "exhirom")
    if offset is None:
        raise ValueError("Entrada fora de ROM")
    state = CpuState(e=False, m=m, x=x)
    out = []
    for _ in range(limit):
        item = decode_one(data, offset, state, "exhirom")
        if item is None:
            break
        cleaned = {k: v for k, v in item.items() if k != "state_after"}
        out.append(cleaned)
        if item.get("ambiguous") or item.get("size") is None:
            break
        state.update(item["mnemonic"], int.from_bytes(
            bytes.fromhex(item["bytes"])[1:], "little") if item["mode"].startswith("imm") else None)
        if item.get("flow") in ("jump", "stop", "unknown"):
            break
        new_offset = next_instruction_offset(offset, item["size"], "exhirom")
        if new_offset is None:
            break
        offset = new_offset
    return {
        "entry_cpu": f"{entry_cpu:06X}", "instructions": out,
        "assumed_status": {"E": 0, "M": int(m), "X": int(x)},
        "warning": "Disassembly linear exploratório; não prova alcançabilidade ou valores de registradores.",
    }


def examine_pair_candidates(data: bytes) -> dict:
    require_arcade(data)
    tables = []
    for addr in PAIR_CANDIDATES:
        raw = read_cpu(data, addr, COUNT * 2)
        tables.append({
            "cpu": f"{addr:06X}", "bytes": raw.hex(" "),
            "words_little_endian": [int.from_bytes(raw[i:i+2], "little")
                                    for i in range(0, len(raw), 2)],
            "meaning": "NÃO VERIFICADO",
        })
    return {"tables": tables, "entry_size_hypothesis": 2,
            "evidence": "BYTES CONFIRMADOS; INTERPRETAÇÃO HIPOTÉTICA"}


def compare_graphics_snapshot(a: bytes, b: bytes, *, kind: str) -> dict:
    if kind not in ("vram", "cgram", "oam"):
        raise ValueError("Tipo de dump inválido")
    validate_dump(kind, a)
    validate_dump(kind, b)
    changed = [i for i, (before, after) in enumerate(zip(a, b)) if before != after]
    spans = []
    for pos in changed:
        if spans and pos == spans[-1][1]:
            spans[-1][1] += 1
        else:
            spans.append([pos, pos+1])
    report = {
        "kind": kind,
        "a_sha256": hashlib.sha256(a).hexdigest(),
        "b_sha256": hashlib.sha256(b).hexdigest(),
        "changed_bytes": len(changed),
        "spans": [{"start": start, "end_exclusive": end, "size": end-start}
                  for start, end in spans[:200]],
        "spans_omitted": max(0, len(spans)-200),
        "evidence": "CONFIRMADO POR COMPARAÇÃO DE DUMPS",
    }
    if kind == "cgram":
        ca, cb = decode_cgram(a), decode_cgram(b)
        report["changed_palette_entries"] = [
            {"index": i, "before": list(ca[i]), "after": list(cb[i])}
            for i in range(256) if ca[i] != cb[i]]
    if kind == "vram":
        report["changed_4bpp_tile_indices"] = [
            i for i in range(len(a)//32) if a[i*32:(i+1)*32] != b[i*32:(i+1)*32]
        ]
        report["warning"] = "Tiles de 4bpp são candidatos; o formato real depende do modo PPU."
    return report


def investigate(data: bytes) -> dict:
    require_arcade(data)
    return {
        "selection": extract_selection(data),
        "disassembly": [disassemble_window(data, addr) for addr in ENTRY_POINTS],
        "word_candidates": examine_pair_candidates(data),
        "limitations": [
            "Nomes são correlação com o changelog, não trace de luta.",
            "Não identifica automaticamente ponteiros de retratos.",
            "Não identifica codec proprietário de compressão.",
            "DMA exige logs de escritas efetivas; o trace textual isolado não basta.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UMK3 Research Pipeline v1 (somente leitura)")
    parser.add_argument("rom", type=Path, help="ROM Arcade Edition beta 71 autenticada")
    parser.add_argument("--out", type=Path, help="Relatório JSON; falha se já existir")
    parser.add_argument("--vram-a", type=Path)
    parser.add_argument("--vram-b", type=Path)
    parser.add_argument("--cgram-a", type=Path)
    parser.add_argument("--cgram-b", type=Path)
    parser.add_argument("--oam-a", type=Path)
    parser.add_argument("--oam-b", type=Path)
    args = parser.parse_args(argv)
    result = investigate(args.rom.read_bytes())
    for kind in ("vram", "cgram", "oam"):
        first, second = getattr(args, kind + "_a"), getattr(args, kind + "_b")
        if (first is None) != (second is None):
            parser.error(f"--{kind}-a e --{kind}-b devem ser usados juntos")
        if first is not None:
            result.setdefault("graphics_diffs", {})[kind] = compare_graphics_snapshot(
                first.read_bytes(), second.read_bytes(), kind=kind)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
