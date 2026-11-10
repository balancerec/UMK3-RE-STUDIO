"""Geração segura e determinística de perfis de coleta Mesen Lua.

Não controla o emulador. Só gera código Lua versionado para execução manual no Script Window.
"""
from pathlib import Path
import re

TEMPLATE = Path(__file__).resolve().parents[1] / "tools" / "mesen_bridge" / "capture.lua"
MAX_POINTS = 32
MAX_EVENTS = 20000


def _list_addrs(value: str, *, kind: str) -> list[int]:
    if not value or not value.strip():
        raise ValueError(f"Informe ao menos um endereço {kind}.")
    values = []
    for raw in re.split(r"[;,\s]+", value.strip()):
        if not raw:
            continue
        addr = raw.upper().replace(":", "").removeprefix("$").removeprefix("0X")
        if not re.fullmatch(r"[0-9A-F]{1,6}", addr):
            raise ValueError(f"Endereço hexadecimal inválido: {raw!r}.")
        n = int(addr, 16)
        if kind == "CPU":
            if n > 0xFFFFFF:
                raise ValueError("Endereço CPU fora de 24 bits.")
        else:
            # O offset físico é 0..1FFFF: 128 KiB
            if raw.upper().replace(":", "").removeprefix("$").startswith("7E") and n >= 0x7E0000:
                if n <= 0x7FFFFF:
                    n -= 0x7E0000
            if not 0 <= n <= 0x1FFFF:
                raise ValueError(f"WRAM fora do intervalo 00000-1FFFF: {raw!r}.")
        if n not in values:
            values.append(n)
        if len(values) > MAX_POINTS:
            raise ValueError(f"Máximo de {MAX_POINTS} endereços por categoria.")
    if not values:
        raise ValueError("A lista de endereços está vazia.")
    return values


def generate_capture_script(
    pc: str = "86A353",
    cpu_points: str = "86A353,86A355,86A385,86A733,86A738,86A73A,86A7A8",
    wram_points: str = "0C0E,3A50,36D0,52C8,1C59",
    session_id: str = "exp001_run01",
    max_events: int = 20000,
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", session_id):
        raise ValueError("session_id: use 1–48 caracteres alfanuméricos, '-' ou '_'.")
    if not 1 <= max_events <= MAX_EVENTS:
        raise ValueError("max_events precisa estar entre 1 e 20000.")
    start = _list_addrs(pc, kind="CPU")
    if len(start) != 1:
        raise ValueError("Informe um único PC inicial.")
    cpu = _list_addrs(cpu_points, kind="CPU")
    if start[0] not in cpu:
        cpu.insert(0, start[0])
    wram = _list_addrs(wram_points, kind="WRAM")
    source = TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        r'local SESSION_ID = "exp001_run01"': f'local SESSION_ID = "{session_id}"',
        'local MAX_EVENTS = 20000': f'local MAX_EVENTS = {max_events}',
        'local cpu_points = {0x86A353, 0x86A355, 0x86A385, 0x86A733, 0x86A738, 0x86A73A, 0x86A7A8}':
            'local cpu_points = {' + ', '.join(f'0x{x:06X}' for x in cpu) + '}',
        'local wram_points = {0x0C0E, 0x3A50, 0x36D0, 0x52C8, 0x1C59}':
            'local wram_points = {' + ', '.join(f'0x{x:05X}' for x in wram) + '}',
    }
    for old, new in replacements.items():
        if source.count(old) != 1:
            raise RuntimeError(f"Template Lua incompatível: {old}")
        source = source.replace(old, new, 1)
    return source
