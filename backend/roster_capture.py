"""Version-scoped, read-only comparison of SNES WRAM/VRAM/CGRAM/OAM captures.

No ROM patching, character-ID assignment, or unlock inference.
Run: python -m backend.roster_capture --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

MEMORY_SIZES = {"wram": 0x20000, "vram": 0x10000, "cgram": 0x200, "oam": 0x220}
WATCH = {
    "special_fallback_7e1c59": (0x1C59, 1),
    "resolved_candidate_7e36d0": (0x36D0, 2),
    "p1_roster_index_candidate_7e3a50": (0x3A50, 2),
    "selector_event_candidate_7e3bae": (0x3BAE, 2),
    "selector_event_candidate_7e3bb0": (0x3BB0, 2),
    "stored_character_candidate_7e52c8": (0x52C8, 2),
    "adjacent_character_field_7e52ca": (0x52CA, 2),
}
HEX_LINE = re.compile(r"^(?:[0-9A-Fa-f]{2}(?:[ \t]+|$))+$")
ROM_SHA = re.compile(r"^[0-9a-fA-F]{64}$")
MAX_RANGES = 256


def read_dump(path: str | Path, kind: str) -> bytes:
    """Accept exact-size binary dumps or strictly byte-only ASCII hex dumps."""
    if kind not in MEMORY_SIZES:
        raise ValueError("Tipo de memória inválido")
    raw = Path(path).read_bytes()
    expected = MEMORY_SIZES[kind]
    if len(raw) == expected:
        return raw
    if len(raw) > expected * 4 + 4096:
        raise ValueError("Dump grande demais para um arquivo hexadecimal")
    try:
        decoded = raw.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("Dump não é binário do tamanho esperado nem texto ASCII hexadecimal") from exc
    lines = decoded.splitlines()
    if not lines or not all(HEX_LINE.fullmatch(line.strip()) for line in lines):
        raise ValueError("Use bytes hexadecimais separados por espaços, sem offsets ou anotações")
    result = bytes(int(part, 16) for line in lines for part in line.split())
    if len(result) != expected:
        raise ValueError(f"{kind.upper()} deve ter {expected} bytes; recebeu {len(result)}")
    return result


def details(data: bytes, kind: str) -> dict:
    expected = MEMORY_SIZES[kind]
    if len(data) != expected:
        raise ValueError(f"{kind.upper()} precisa ter exatamente {expected} bytes")
    fields = {}
    if kind == "wram":
        for name, (offset, width) in WATCH.items():
            fields[name] = {
                "address": f"7E:{offset:04X}",
                "value": f"{int.from_bytes(data[offset:offset + width], 'little'):0{width * 2}X}",
                "width_bytes": width,
                "interpretation": "candidate_not_proven",
            }
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "fields": fields}


def compare(a: bytes, b: bytes, kind: str, *, max_ranges: int = MAX_RANGES) -> dict:
    if len(a) != MEMORY_SIZES[kind] or len(b) != MEMORY_SIZES[kind]:
        raise ValueError("Arquivos devem ser dumps completos do mesmo tipo")
    if not 1 <= max_ranges <= 10000:
        raise ValueError("max_ranges fora dos limites")
    total = 0
    ranges = []
    start = None
    bank_counts = {}
    for i, (left, right) in enumerate(zip(a, b)):
        if left != right:
            total += 1
            segment = f"7{('E' if i < 0x10000 else 'F')}" if kind == "wram" else f"{i // 0x100:02X}"
            bank_counts[segment] = bank_counts.get(segment, 0) + 1
            if start is None:
                start = i
        elif start is not None:
            if len(ranges) < max_ranges:
                ranges.append({"start": start, "end_exclusive": i, "length": i - start})
            start = None
    if start is not None and len(ranges) < max_ranges:
        ranges.append({"start": start, "end_exclusive": len(a), "length": len(a) - start})
    fields_changed = []
    if kind == "wram":
        da, db = details(a, kind)["fields"], details(b, kind)["fields"]
        for key, field in da.items():
            if field["value"] != db[key]["value"]:
                fields_changed.append({
                    "field": key, "address": field["address"],
                    "a": field["value"], "b": db[key]["value"],
                    "classification": "value_change_only",
                })
    return {
        "kind": kind, "changed_bytes": total,
        "percent_changed": round(total * 100 / len(a), 4),
        "ranges": ranges,
        "ranges_truncated": total > 0 and _count_ranges(a, b) > len(ranges),
        "changed_by_region": bank_counts,
        "watched_fields_changed": fields_changed,
        "note": "Capturas representam instantes diferentes; diferenças não comprovam alterações de código, gráficos ou desbloqueio.",
    }


def _count_ranges(a: bytes, b: bytes) -> int:
    count = 0
    previous = False
    for left, right in zip(a, b):
        changed = left != right
        if changed and not previous:
            count += 1
        previous = changed
    return count


def report(file_a, file_b, kind, *, version_a, version_b,
           rom_sha_a=None, rom_sha_b=None, label_a=None, label_b=None) -> dict:
    for sha in (rom_sha_a, rom_sha_b):
        if sha is not None and not ROM_SHA.fullmatch(sha):
            raise ValueError("SHA-256 de ROM deve conter 64 dígitos hexadecimais")
    a = read_dump(file_a, kind)
    b = read_dump(file_b, kind)
    return {
        "schema_version": 1,
        "source": "offline_snapshot_comparison",
        "observed_execution": False,
        "a": {"declared_version": version_a, "rom_sha256_claimed": rom_sha_a,
              "label": label_a, **details(a, kind)},
        "b": {"declared_version": version_b, "rom_sha256_claimed": rom_sha_b,
              "label": label_b, **details(b, kind)},
        "comparison": compare(a, b, kind),
        "limitations": [
            "Versão e SHA da ROM são rótulos fornecidos pelo operador; não são validados a partir do dump.",
            "Um snapshot não identifica quem escreveu cada endereço.",
            "O valor 001B não comprova sozinho a identidade ou o desbloqueio de um personagem.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Comparador de snapshots Mesen, sem modificar ROM.")
    parser.add_argument("--kind", required=True, choices=MEMORY_SIZES)
    parser.add_argument("--a", required=True, help="Primeiro dump binário ou texto hexadecimal")
    parser.add_argument("--b", required=True, help="Segundo dump binário ou texto hexadecimal")
    parser.add_argument("--version-a", required=True)
    parser.add_argument("--version-b", required=True)
    parser.add_argument("--rom-sha-a")
    parser.add_argument("--rom-sha-b")
    parser.add_argument("--label-a")
    parser.add_argument("--label-b")
    parser.add_argument("--output", help="Arquivo JSON opcional")
    args = parser.parse_args(argv)
    try:
        payload = report(args.a, args.b, args.kind, version_a=args.version_a,
                         version_b=args.version_b, rom_sha_a=args.rom_sha_a,
                         rom_sha_b=args.rom_sha_b, label_a=args.label_a, label_b=args.label_b)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(result + "\n", encoding="utf-8")
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
