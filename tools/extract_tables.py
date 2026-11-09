"""Extrai as tabelas do Hidden Roster da ROM local e grava JSON/CSV/Markdown.

Uso (na raiz do repositório):
    python -m tools.extract_tables CAMINHO/DA/ROM.sfc [pasta_saida]

A ROM nunca é copiada; só as tabelas pequenas derivadas dela.
"""
import csv, hashlib, json, sys
from pathlib import Path
from backend.core import Rom, cpu_to_file
from backend import hidden_roster as hr


def main(argv):
    if not argv:
        print(__doc__); return 2
    raw = Path(argv[0]).read_bytes()
    out = Path(argv[1]) if len(argv) > 1 else Path('docs/data')
    out.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(raw).hexdigest()
    rom = Rom(raw)
    print(f'SHA-256: {sha}  ({"confere" if sha == hr.ROM_SHA256 else "DIFERE do hash registrado!"})')
    print(f'mapeamento={rom.mapping} header={rom.header}')
    t = hr.read_tables(rom)
    with open(out / 'tabela_86A207_ids.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['indice', 'id_hex', 'id_dec', 'nome', 'status_nome', 'cpu', 'rom_offset'])
        for i, v in enumerate(t['ids']):
            name, st = hr.CHARACTERS.get(v, ('oculto/via $7E:1C59' if v == 0xFF else '', 'NÃO VERIFICADO' if v != 0xFF else 'CONFIRMADO'))
            cpu = hr.ID_TABLE_CPU + i
            w.writerow([f'0x{i:02X}', f'0x{v:02X}', v, name, st, f'${cpu >> 16:02X}:{cpu & 0xFFFF:04X}', f'0x{cpu_to_file(cpu, rom.mapping):06X}'])
    with open(out / 'tabelas_navegacao.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['indice'] + list(t['nav']))
        for i in range(hr.ID_TABLE_LEN):
            w.writerow([f'0x{i:02X}'] + [f'0x{t["nav"][k][i]:02X}' for k in t['nav']])
    (out / 'hidden_roster.json').write_text(json.dumps({
        'rom_sha256': sha, 'sha256_confere': sha == hr.ROM_SHA256, 'mapping': rom.mapping,
        'ids': t['ids'].hex(' '), 'nav': {k: v.hex(' ') for k, v in t['nav'].items()},
        'writes_1C59': hr.scan_wram_writes(rom.data, 0x1C59, rom.mapping),
        'writes_3BAE': hr.scan_wram_writes(rom.data, 0x3BAE, rom.mapping),
        'writes_3BB0': hr.scan_wram_writes(rom.data, 0x3BB0, rom.mapping),
    }, indent=1, ensure_ascii=False))
    print(f'Gravado em {out}/')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
