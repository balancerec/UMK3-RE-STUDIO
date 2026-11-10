"""Decision Trace Diff v3: compara duas decisões registradas pelo Mesen 2.

Compara comportamento observado, sem equiparar mudança de registrador a
causa de bloqueio. Somente CPU 65C816; SPC700 permanece contado à parte.
"""
from __future__ import annotations

from collections import deque
from difflib import SequenceMatcher

from .trace65816 import parse_line, wram_address, BRANCHES

MAX_TRACE_BYTES = 128 * 1024 * 1024
TARGET = 0x3A50
ANCHOR_PC = 0x86A7A8


def _pc(pc):
    return f"${pc >> 16:02X}:{pc & 0xffff:04X}"


def _canonical(pc):
    # Espelho físico ExHiROM dos bancos 80-BF em C0-FF;
    # comparar o PC literal também para evitar ambiguidades.
    bank = pc >> 16
    return ((bank + 0x40) << 16 | (pc & 0xFFFF)) if 0x80 <= bank <= 0xBF else pc


def _event(line, next_line=None):
    result = {
        "line": line.seq, "pc": _pc(line.pc), "pc_canonical": _pc(_canonical(line.pc)),
        "instruction": line.text, "registers": line.regs,
        "effective_address": f"${line.ea:06X}" if line.ea is not None else None,
        "memory_before": line.mem_value,
    }
    if line.mnemonic in BRANCHES and next_line is not None:
        target = None
        op = line.operand.strip().lstrip("$")
        try:
            target = int(op, 16)
            if len(op) <= 4:
                target |= line.pc & 0xFF0000
        except ValueError:
            pass
        fallthrough = ((line.pc & 0xFF0000) | ((line.pc + (line.length or 2)) & 0xFFFF))
        if target is not None:
            if next_line.pc == target:
                outcome = "taken"
            elif next_line.pc == fallthrough:
                outcome = "not_taken"
            else:
                outcome = "unknown"
            result["branch"] = {"target": _pc(target), "outcome": outcome,
                                "next_pc": _pc(next_line.pc)}
    return result


def _parse(raw):
    if len(raw) > MAX_TRACE_BYTES:
        raise ValueError("Trace excede o limite de 128 MiB")
    text = raw.decode("utf-8-sig", errors="replace")
    cpu, spc = [], 0
    for seq, row in enumerate(text.splitlines(), 1):
        line = parse_line(row, seq)
        if line is None:
            continue
        if line.cpu == "SPC700":
            spc += 1
        else:
            cpu.append(line)
    return cpu, spc, len(text.splitlines())


def _is_anchor(line):
    if line.mnemonic != "sta":
        return False
    if wram_address(line.ea) == TARGET:
        return True
    # PC conhecido; sem endereço efetivo não se deve alegar gravação confirmada.
    return _canonical(line.pc) == _canonical(ANCHOR_PC)


def _select(cpu, ordinal, lookback):
    matches = [i for i, item in enumerate(cpu) if _is_anchor(item)]
    if not matches:
        return {"found": False, "anchors": 0, "reason": "Nenhum STA associado a $7E:3A50 encontrado."}
    if ordinal < 1 or ordinal > len(matches):
        raise ValueError(f"ordinal deve estar entre 1 e {len(matches)}")
    ix = matches[ordinal - 1]
    start = max(0, ix - lookback)
    window = [_event(cpu[j], cpu[j + 1] if j + 1 < len(cpu) else None)
              for j in range(start, ix + 1)]
    anchor = cpu[ix]
    effective = wram_address(anchor.ea) == TARGET
    width_known = anchor.flags.get("m") is not None
    written = (anchor.regs["A"] & (0xFF if anchor.flags.get("m") else 0xFFFF)) if "A" in anchor.regs and width_known else None
    return {
        "found": True, "anchors": len(matches),
        "anchor": _event(anchor, cpu[ix + 1] if ix + 1 < len(cpu) else None),
        "address_confirmed": effective, "target": "$7E:3A50",
        "value_before": anchor.mem_value, "value_after_derived": written,
        "confidence": "DERIVADO" if written is not None and effective else "NÃO VERIFICADO",
        "cursor": {0x0003: "Jax", 0x0010: "Ermac", 0x000A: "slot oculto"}.get(written, "outro/desconhecido"),
        "window": window,
        "truncated_before": start == 0,
    }


def compare_traces(raw_a: bytes, raw_b: bytes, *, ordinal_a: int = 1,
                   ordinal_b: int = 1, lookback: int = 160):
    """Retorna janelas e diferenças observadas; não infere causalidade."""
    if not 1 <= lookback <= 1000:
        raise ValueError("lookback deve estar entre 1 e 1000")
    a, spc_a, lines_a = _parse(raw_a)
    b, spc_b, lines_b = _parse(raw_b)
    left = _select(a, ordinal_a, lookback)
    right = _select(b, ordinal_b, lookback)
    result = {
        "version": "decision-trace-diff-v3.0",
        "read_only": True,
        "meta": {"a": {"lines": lines_a, "cpu": len(a), "spc": spc_a},
                 "b": {"lines": lines_b, "cpu": len(b), "spc": spc_b}},
        "a": left, "b": right, "differences": [], "branch_differences": [],
        "limitations": [
            "Comparação de traces não prova causalidade nem condição de desbloqueio.",
            "Valor após = no Mesen representa a memória antes da instrução.",
            "O valor gravado deriva de A/P e não está confirmado sem leitura posterior.",
            "As janelas podem começar após a decisão causal; amplie a captura nesse caso.",
        ],
    }
    if not left["found"] or not right["found"]:
        return result
    wa, wb = left["window"], right["window"]
    # Alinha pelos PCs das instruções, preservando a ordem e repetições.
    ka = [e["pc_canonical"] for e in wa]
    kb = [e["pc_canonical"] for e in wb]
    matcher = SequenceMatcher(a=ka, b=kb, autojunk=False)
    diffs, branch_diffs = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            diffs.append({"type": "control_flow", "kind": tag,
                          "a": wa[i1:i2][:12], "b": wb[j1:j2][:12]})
            continue
        for i, j in zip(range(i1, i2), range(j1, j2)):
            ea, eb = wa[i], wb[j]
            if ea.get("branch") and eb.get("branch") and ea["branch"]["outcome"] != eb["branch"]["outcome"]:
                branch_diffs.append({"pc": ea["pc"], "a": ea["branch"], "b": eb["branch"],
                                     "line_a": ea["line"], "line_b": eb["line"]})
            if ea["memory_before"] is not None and eb["memory_before"] is not None and ea["memory_before"] != eb["memory_before"]:
                diffs.append({"type": "memory_value", "pc": ea["pc"],
                              "line_a": ea["line"], "line_b": eb["line"],
                              "a": ea["memory_before"], "b": eb["memory_before"],
                              "address_a": ea["effective_address"], "address_b": eb["effective_address"]})
            elif ea["registers"] != eb["registers"]:
                # Só registrar divergência em registradores relevantes, não ruído generalizado de X/Y.
                changed = {r: [ea["registers"].get(r), eb["registers"].get(r)]
                           for r in ("A", "P", "D", "DB") if ea["registers"].get(r) != eb["registers"].get(r)}
                if changed:
                    diffs.append({"type": "registers", "pc": ea["pc"], "line_a": ea["line"],
                                  "line_b": eb["line"], "changes": changed})
    result["differences"] = diffs[:150]
    result["branch_differences"] = branch_diffs[:100]
    result["summary"] = {
        "a_destination": left["cursor"], "b_destination": right["cursor"],
        "same_target": left["value_after_derived"] == right["value_after_derived"],
        "different_branch_outcomes": len(branch_diffs),
        "control_flow_differences": sum(d["type"] == "control_flow" for d in diffs),
        "first_difference": diffs[0] if diffs else None,
        "interpretation": "Pontos candidatos para investigação manual; nenhuma causa foi demonstrada.",
    }
    return result
