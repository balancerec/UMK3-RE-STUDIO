"""CLI do estudo do slot 0x0A (Dragão): relatório estático da ROM e impacto de um IPS nas regiões do seletor.

Somente leitura: nunca grava sobre a ROM nem sobre o IPS de entrada.
  python -m tools.dragon_slot_report analyze ROM.sfc [--json out.json] [--md out.md]
  python -m tools.dragon_slot_report ips-impact ROM.sfc patch.ips [--json out.json]
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from backend.core import Rom
from backend import dragon_slot as D

# Regiões do seletor na ROM Deluxe 2.2 (offsets de arquivo, fim exclusivo). Origem: desmontagem + fatos de dragon_slot.
REGIONS = [
    ('id_e_tabelas_direcionais', 0x06A1F6, 0x06A726),
    ('despacho_cursor', 0x06A726, 0x06A79C),
    ('retrato_dragao', 0x04A270, 0x04A2F4),
    ('processos_abrir_fechar', 0x04A38E, 0x04A430),
    ('rodizio_ocultos', 0x04A328, 0x04A38E),
    ('rodizio_bloco_FFFE30', 0x3FFE30, 0x3FFEB0),
]


def parse_ips(blob: bytes):
    if not blob.startswith(b'PATCH'):
        raise ValueError('cabeçalho IPS inválido')
    i, out = 5, []
    while blob[i:i + 3] != b'EOF':
        off = int.from_bytes(blob[i:i + 3], 'big'); size = int.from_bytes(blob[i + 3:i + 5], 'big'); i += 5
        if size == 0:
            n = int.from_bytes(blob[i:i + 2], 'big'); payload = bytes([blob[i + 2]]) * n; i += 3
        else:
            payload = blob[i:i + size]; i += size
        out.append((off, payload))
    return out


def ips_impact(rom_bytes: bytes, ips: bytes) -> dict:
    recs = parse_ips(ips)
    rom_len = len(rom_bytes)
    res = {'rom_sha256': hashlib.sha256(rom_bytes).hexdigest(), 'records': len(recs),
           'bytes_written': sum(len(p) for _, p in recs),
           'beyond_rom_end': sum(1 for o, _ in recs if o >= rom_len), 'regions': []}
    for name, a, b in REGIONS:
        changed = []
        for off, p in recs:
            lo, hi = max(a, off), min(b, off + len(p))
            for pos in range(lo, hi):
                old, new = rom_bytes[pos], p[pos - off]
                if old != new:
                    changed.append({'offset': f'0x{pos:06X}', 'old': f'{old:02X}', 'new': f'{new:02X}'})
        res['regions'].append({'region': name, 'range': f'0x{a:06X}..0x{b:06X}', 'changed_bytes': len(changed), 'changes': changed[:64]})
    return res


def to_markdown(a: dict) -> str:
    d = a['dispatch']
    L = ['# Slot 0x0A (Dragão) — relatório estático', '',
         f"Rotina de despacho: {d.get('cpu')} (offset {d.get('rom_offset')}), localizada por: {d.get('how_located')}", '',
         f"Índice especial {d.get('special_index')}, libera com $1C57 == {d.get('state_gate_value')}.", '',
         '| Direção | Redireciona para o índice | Eixo dobrado |', '|---|---|---|']
    for k, r in d.get('redirects', {}).items():
        L.append(f"| {k} | 0x{r['target_index']:02X} | {r['axis']} |")
    for k, v in a.get('reachability', {}).items():
        L += ['', f"Alcançáveis com {k}: {len(v['reachable'])}/24; inalcançáveis: {v['unreachable']}"]
    L += ['', 'Todos os fatos abaixo foram lidos da ROM (classe ESTÁTICO-CONFIRMADO salvo indicação).', '']
    for sec in ('state_1c57', 'portrait', 'cycle'):
        for f in a[sec]['facts']:
            L.append(f"- [{f['class']}] {f['cpu']} `{f['bytes']}` — {f['text']}")
    return '\n'.join(L) + '\n'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('analyze'); a.add_argument('rom'); a.add_argument('--json'); a.add_argument('--md')
    i = sub.add_parser('ips-impact'); i.add_argument('rom'); i.add_argument('ips'); i.add_argument('--json')
    args = ap.parse_args(argv)
    data = Path(args.rom).read_bytes()
    if args.cmd == 'analyze':
        rom = Rom(data, Path(args.rom).name)
        res = D.analyze(rom)
        res.pop('_nav', None)
        res['rom_sha256'] = hashlib.sha256(rom.data).hexdigest()
        res['rom_is_deluxe_2_2'] = res['rom_sha256'] == D.ROM_SHA256
        if args.json: Path(args.json).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
        md = to_markdown(res)
        if args.md: Path(args.md).write_text(md, encoding='utf-8')
        else: print(md)
        return 0
    res = ips_impact(data, Path(args.ips).read_bytes())
    txt = json.dumps(res, indent=1, ensure_ascii=False)
    if args.json: Path(args.json).write_text(txt, encoding='utf-8')
    else: print(txt)
    return 0


if __name__ == '__main__':
    sys.exit(main())
