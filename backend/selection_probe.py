"""Investigação conservadora do slot 000A em traces 65C816 do Mesen.

Somente leitura. Sem conversões especulativas CPU→ROM nem alteração de ROMs.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from .trace65816 import parse_line, wram_address

WATCH = {
    0x0C0E: "temporary_index", 0x1C57: "special_state",
    0x3A50: "cursor_p1", 0x36D0: "logical_identity",
    0x52C8: "synchronized_identity", 0x1C59: "hidden_identity",
}
CHECKPOINTS = {
    0x86A73A: "compare_000A", 0x86A73F: "read_special_state",
    0x86A767: "redirect_jax_load", 0x86A76A: "redirect_jax_store",
    0x86A777: "redirect_ermac_load", 0x86A77A: "redirect_ermac_store",
    0x86A7A8: "cursor_commit",
}

def _hex(value):
    return None if value is None else f"{value:04X}"

def _write_candidate(line):
    """STA/STZ: valor derivado do registrador anterior à execução."""
    m = line.flags.get("m")
    if m is None or line.mnemonic not in ("sta", "stz"):
        return None
    if line.mnemonic == "stz":
        return 0
    a = line.regs.get("A")
    return None if a is None else a & (0xFF if m else 0xFFFF)

def analyze_lines(lines):
    """Analisa TraceLine do parser existente e retorna relatório JSON-safe."""
    counts = Counter()
    observations, cursor_writes, state_accesses = [], [], []
    observed_state_reads = set()
    for line in lines:
        if line is None or line.cpu != "65C816":
            continue
        counts["cpu_lines"] += 1
        addr = wram_address(line.ea) if line.ea is not None else None
        pc = line.pc
        event = {
            "line": line.seq,
            "pc": f"{pc >> 16:02X}:{pc & 0xFFFF:04X}",
            "instruction": line.text,
            "checkpoint": CHECKPOINTS.get(pc),
            "effective_address": f"7E:{addr:04X}" if addr is not None and addr < 0x10000 else None,
            "address_basis": line.ea_basis,
            "read_before": _hex(line.mem_value),
            "written_derived": None,
            "confidence": "NÃO VERIFICADO",
        }
        if addr in WATCH:
            event["variable"] = WATCH[addr]
            counts[f"access_{WATCH[addr]}"] += 1
            if line.mnemonic in ("sta", "stz"):
                event["written_derived"] = _hex(_write_candidate(line))
                if line.ea_basis == "trace" and event["written_derived"] is not None:
                    event["confidence"] = "DERIVADO"
            elif line.mem_value is not None and line.ea_basis == "trace":
                event["confidence"] = "CONFIRMADO POR TRACE (valor anterior/leitura)"
        if pc in CHECKPOINTS or addr in WATCH:
            observations.append(event)
        if addr == 0x3A50 and line.mnemonic in ("sta", "stz"):
            cursor_writes.append(event)
        if addr == 0x1C57:
            state_accesses.append(event)
            if (line.mnemonic in ("lda", "cmp", "bit")
                    and line.mem_value is not None and line.ea_basis == "trace"):
                observed_state_reads.add(_hex(line.mem_value))
    destinations = Counter(e["written_derived"] for e in cursor_writes
                           if e["written_derived"] is not None)
    return {
        "version": "selection-probe-v1", "read_only": True,
        "counts": dict(counts),
        "observed_state_values": sorted(observed_state_reads),
        "cursor_destinations_derived": dict(destinations),
        "cursor_writes": cursor_writes,
        "state_accesses": state_accesses,
        "observations": observations,
        "limitations": [
            "Traces não demonstram que caminhos ausentes sejam impossíveis.",
            "Valor pós-STA é derivado, não confirmado sem leitura posterior.",
            "Índice do cursor não determina sozinho identidade ou retrato.",
            "Escritas indiretas sem endereço efetivo não são associadas à WRAM.",
            "Transições de $1C57 precisam de confirmação pós-escrita.",
        ],
    }

def analyze_trace(data: bytes):
    if len(data) > 128 * 1024 * 1024:
        raise ValueError("Trace excede 128 MiB")
    lines = (parse_line(row, i) for i, row in enumerate(
        data.decode("utf-8-sig", errors="replace").splitlines(), 1))
    return analyze_lines(lines)

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="UMK3: investigação read-only do slot 000A")
    ap.add_argument("trace", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    report = json.dumps(analyze_trace(args.trace.read_bytes()),
                        indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with args.out.open("x", encoding="utf-8") as f:
            f.write(report)
    else:
        print(report, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
