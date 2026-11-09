"""ROM Patch Lab: deterministic, read-only comparison and IPS patch generation.

No imports from the Studio API: this module can run alongside trace analysis.
IPS uses 24-bit offsets and cannot encode a record starting at the EOF marker.
For safety this implementation requires equal ROM sizes and rejects that offset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

IPS_EOF = 0x454F46
IPS_MAX_OFFSET = 0xFFFFFF
MAX_ROM_SIZE = 16 * 1024 * 1024 + 512


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_rom(data: bytes) -> None:
    if not (32768 <= len(data) <= MAX_ROM_SIZE):
        raise ValueError("ROM fora do limite permitido (32 KiB–16 MiB + 512 bytes)")
    if len(data) % 32768 not in (0, 512):
        raise ValueError("Tamanho incompatível com imagem SNES comum")


def _regions(original: bytes, modified: bytes):
    """Yield maximal contiguous changed regions as (start, bytes)."""
    if len(original) != len(modified):
        raise ValueError("As ROMs precisam ter o mesmo tamanho; redimensionamento não suportado")
    i = 0
    n = len(original)
    while i < n:
        if original[i] == modified[i]:
            i += 1
            continue
        start = i
        while i < n and original[i] != modified[i]:
            i += 1
        yield start, modified[start:i]


def compare_roms(original: bytes, modified: bytes, *, max_regions: int = 200) -> dict:
    if len(original) != len(modified):
        raise ValueError("As ROMs precisam ter o mesmo tamanho; redimensionamento não suportado")
    _validate_rom(original)
    _validate_rom(modified)
    if max_regions < 0:
        raise ValueError("max_regions deve ser >= 0")
    regions = []
    total_regions = 0
    bytes_changed = 0
    for start, payload in _regions(original, modified):
        total_regions += 1
        bytes_changed += len(payload)
        if len(regions) < max_regions:
            regions.append({
                "offset": f"0x{start:06X}",
                "length": len(payload),
                "before": original[start:start + min(len(payload), 16)].hex(" "),
                "after": payload[:16].hex(" "),
            })
    return {
        "size": len(original),
        "header_bytes": 512 if len(original) % 32768 == 512 else 0,
        "original_sha256": sha256(original),
        "modified_sha256": sha256(modified),
        "changed_bytes": bytes_changed,
        "regions_total": total_regions,
        "regions_in_report": regions,
        "regions_omitted": total_regions - len(regions),
        "identical": bytes_changed == 0,
    }


def make_ips(original: bytes, modified: bytes) -> bytes:
    """Generate an IPS patch without overwriting either source ROM.

    IPS records split at 65535 bytes. The reserved offset 0x454F46 ('EOF')
    must never be used as a record header. If a run spans it, the preceding
    record is extended to cover that byte when possible.
    """
    _validate_rom(original)
    _validate_rom(modified)
    data = bytearray(b"PATCH")
    for start, payload in _regions(original, modified):
        position = start
        end = start + len(payload)
        while position < end:
            if position > IPS_MAX_OFFSET:
                raise ValueError("IPS não suporta offsets além de 0xFFFFFF")
            # A byte at 0x454F46 is legal ROM data, but this value cannot
            # start an IPS record. Include the preceding unchanged byte.
            record_start = position - 1 if position == IPS_EOF else position
            length = min(65535, end - record_start)
            # Avoid placing the next record on the reserved marker.
            if record_start < IPS_EOF and record_start + length == IPS_EOF and end > IPS_EOF:
                if length < 65535:
                    length += 1
                else:
                    length -= 1
            if record_start > IPS_MAX_OFFSET:
                raise ValueError("IPS não suporta offsets além de 0xFFFFFF")
            data.extend(record_start.to_bytes(3, "big"))
            data.extend(length.to_bytes(2, "big"))
            data.extend(modified[record_start:record_start + length])
            position = record_start + length
    data.extend(b"EOF")
    return bytes(data)


def apply_ips(original: bytes, patch: bytes) -> bytes:
    """Apply a generated/standard IPS patch in memory; never overwrite input."""
    _validate_rom(original)
    if not patch.startswith(b"PATCH"):
        raise ValueError("Cabeçalho IPS inválido")
    result = bytearray(original)
    i = 5
    while True:
        if i + 3 > len(patch):
            raise ValueError("IPS truncado")
        if patch[i:i + 3] == b"EOF":
            if i + 3 != len(patch):
                raise ValueError("IPS com bytes inesperados após EOF; redimensionamento não suportado")
            return bytes(result)
        offset = int.from_bytes(patch[i:i + 3], "big")
        i += 3
        if i + 2 > len(patch):
            raise ValueError("Tamanho de registro IPS ausente")
        size = int.from_bytes(patch[i:i + 2], "big")
        i += 2
        if size == 0:
            if i + 3 > len(patch):
                raise ValueError("Registro RLE truncado")
            count = int.from_bytes(patch[i:i + 2], "big")
            value = patch[i + 2]
            i += 3
            payload = bytes([value]) * count
        else:
            if i + size > len(patch):
                raise ValueError("Registro IPS truncado")
            payload = patch[i:i + size]
            i += size
        if offset + len(payload) > len(result):
            raise ValueError("Registro IPS fora do tamanho da ROM original")
        result[offset:offset + len(payload)] = payload


def _read_rom(path: Path) -> bytes:
    data = path.read_bytes()
    _validate_rom(data)
    return data


def _write_new(path: Path, payload: bytes) -> None:
    # x+b refuses existing files. Never overwrite source images or artifacts.
    with path.open("xb") as f:
        f.write(payload)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UMK3 ROM Patch Lab (IPS, SHA-256 e diff)")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_cmd = sub.add_parser("inspect", help="Hash e metadados básicos da ROM")
    inspect_cmd.add_argument("rom", type=Path)

    diff_cmd = sub.add_parser("diff", help="Comparar duas ROMs sem modificá-las")
    diff_cmd.add_argument("original", type=Path)
    diff_cmd.add_argument("modified", type=Path)
    diff_cmd.add_argument("--report", type=Path)
    diff_cmd.add_argument("--ips", type=Path)

    verify_cmd = sub.add_parser("verify", help="Verificar patch IPS contra hash esperado")
    verify_cmd.add_argument("original", type=Path)
    verify_cmd.add_argument("ips", type=Path)
    verify_cmd.add_argument("--expected-sha256", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            original = _read_rom(args.rom)
            result = {"size": len(original),
                      "header_bytes": 512 if len(original) % 32768 == 512 else 0,
                      "sha256": sha256(original)}
        elif args.command == "diff":
            original, modified = _read_rom(args.original), _read_rom(args.modified)
            result = compare_roms(original, modified)
            if args.ips is not None:
                patch = make_ips(original, modified)
                if apply_ips(original, patch) != modified:
                    raise ValueError("Falha na verificação de round-trip IPS")
                _write_new(args.ips, patch)
                result["ips_file"] = str(args.ips)
                result["ips_bytes"] = len(patch)
            if args.report is not None:
                _write_new(args.report, (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        else:
            original = _read_rom(args.original)
            patched = apply_ips(original, args.ips.read_bytes())
            expected = args.expected_sha256.lower()
            if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
                raise ValueError("SHA-256 esperado inválido")
            actual = sha256(patched)
            result = {"expected_sha256": expected, "actual_sha256": actual, "match": actual == expected}
            if not result["match"]:
                print(json.dumps(result, indent=2))
                return 1
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Erro: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
