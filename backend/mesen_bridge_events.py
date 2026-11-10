"""Leitor de eventos JSONL do Mesen Bridge (somente leitura, recursos limitados)."""
import json
import re
from collections import Counter

MAX_EVENTS = 20000
MAX_BYTES = 16 * 1024 * 1024
HEX_ADDRESS = re.compile(r"^[0-9A-Fa-f]{1,6}$")


def normalize_wram_address(value: int) -> int:
    """Normalize SNES bus $7E/$7F or 128 KiB physical WRAM offsets.

    Mesen's callback may return an absolute bus address for some mappings
    and a low physical address for others; keep original addresses too.
    """
    if 0x7E0000 <= value <= 0x7FFFFF:
        value -= 0x7E0000
    if not 0 <= value <= 0x1FFFF:
        raise ValueError("Endereço WRAM fora do intervalo físico 00000-1FFFF.")
    return value


def analyze_capture_jsonl(payload: bytes) -> dict:
    if len(payload) > MAX_BYTES:
        raise ValueError("Arquivo excede 16 MiB.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("JSONL precisa estar em UTF-8.") from exc
    counts = Counter()
    touched = Counter()
    pc_hits = Counter()
    recent = []
    total = 0
    prev_seq = 0
    session_id = None
    uncertain = 0
    for line_num, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        total += 1
        if total > MAX_EVENTS:
            raise ValueError("Limite de 20000 eventos por importação.")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON inválido na linha {line_num}: {exc.msg}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"Linha {line_num}: objeto JSON esperado.")
        if event.get("schema_version") != "0.1":
            raise ValueError(f"Linha {line_num}: schema_version não suportado.")
        sid = event.get("session_id")
        if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", sid):
            raise ValueError(f"Linha {line_num}: session_id inválido.")
        if session_id is None:
            session_id = sid
        if session_id != sid:
            raise ValueError(f"Linha {line_num}: sessão misturada.")
        seq = event.get("seq")
        if type(seq) is not int or seq <= prev_seq:
            raise ValueError(f"Linha {line_num}: seq deve crescer estritamente.")
        prev_seq = seq
        kind = event.get("kind")
        if kind not in ("cpu_execute", "memory_write"):
            raise ValueError(f"Linha {line_num}: kind inválido.")
        mem = event.get("memory_space")
        if mem not in ("CPU", "WRAM"):
            raise ValueError(f"Linha {line_num}: memory_space inválido.")
        if (kind == "cpu_execute") != (mem == "CPU"):
            raise ValueError(f"Linha {line_num}: kind e memory_space incompatíveis.")
        address = event.get("address")
        if not isinstance(address, str) or not HEX_ADDRESS.fullmatch(address):
            raise ValueError(f"Linha {line_num}: endereço inválido.")
        address_int = int(address, 16)
        raw_address = address.upper().zfill(6)
        if mem == "WRAM":
            try:
                address_int = normalize_wram_address(address_int)
            except ValueError as exc:
                raise ValueError(f"Linha {line_num}: {exc}") from exc
            canonical_address = f"{address_int:05X}"
        else:
            canonical_address = f"{address_int:06X}"
        status = event.get("value_after_status")
        if status not in ("confirmed", "derived", "unknown"):
            raise ValueError(f"Linha {line_num}: status inválido.")
        if status == "unknown":
            uncertain += 1
        regs = event.get("registers")
        if not isinstance(regs, dict) or len(regs) > 256:
            raise ValueError(f"Linha {line_num}: registers inválidos.")
        counts[kind] += 1
        touched[mem + ":" + canonical_address] += 1
        if kind == "cpu_execute":
            pc_hits[canonical_address] += 1
        if len(recent) >= 100:
            recent.pop(0)
        # Enviar somente os campos previstos (não refletir JSON arbitrário).
        recent.append({
            "seq": seq, "kind": kind, "memory_space": mem,
            "address": canonical_address,
            "raw_address": raw_address,
            "callback_value": event.get("callback_value"),
            "value_after_status": status,
        })
    if not total:
        raise ValueError("Nenhum evento JSONL encontrado.")
    return {
        "schema_version": "0.1", "session_id": session_id,
        "events": total, "last_seq": prev_seq,
        "events_by_type": dict(counts),
        "observed_addresses": [{"address": k, "hits": v} for k, v in touched.most_common(100)],
        "cpu_hotspots": [{"pc": k, "hits": v} for k, v in pc_hits.most_common(50)],
        "unknown_after_values": uncertain,
        "recent_events": recent,
        "notice": "Eventos observados, não instruções totais. callback_value não confirma gravação concluída. Não inferir unlock flags."
    }
