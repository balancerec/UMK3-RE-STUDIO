"""Hidden Roster Engine: leitura das tabelas de seleção e simulador de resolução.

Todos os endereços abaixo foram confirmados contra a ROM Deluxe 2.2
(SHA-256 f512ef86...) por conferência de bytes com o disassembly observado no
Mesen. Ver docs/EVIDENCIAS.md. Este módulo descreve comportamento observado;
não substitui o código original do jogo.
"""
from __future__ import annotations
import hashlib
from .core import cpu_to_file, file_to_cpu

ROM_SHA256 = 'f512ef861f0df2dbb8f9563fb5f3b01ab70b7048ac329a9262ff3d34ca487bdd'

ID_TABLE_CPU = 0x86A207      # byte table: cursor index -> character id (0xFF = slot oculto)
ID_TABLE_LEN = 24            # INFERIDO: o código em $86:A21F começa logo após o índice 0x17
HIDDEN_INDEX = 0x0A
HIDDEN_MARK = 0xFF
# Tabelas índice->próximo índice, 24 bytes cada, selecionadas por bit do pad ($0A)
NAV_TABLES = {'up': (0x86A6C6, 0x0800), 'down': (0x86A6DE, 0x0400),
              'left': (0x86A6F6, 0x0200), 'right': (0x86A70E, 0x0100)}

# id -> (nome, status). Só entram IDs com evidência; o resto fica sem nome.
CHARACTERS = {
    0x01: ('Sonya', 'CONFIRMADO'), 0x02: ('Jax', 'CONFIRMADO'), 0x03: ('Nightwolf', 'CONFIRMADO'),
    0x05: ('Stryker', 'CONFIRMADO'), 0x09: ('Kung Lao', 'CONFIRMADO'), 0x0A: ('Kabal', 'CONFIRMADO'),
    0x0B: ('Sheeva', 'CONFIRMADO'), 0x0C: ('Shang Tsung', 'CONFIRMADO'), 0x10: ('Jade', 'CONFIRMADO'),
    0x13: ('Reptile', 'CONFIRMADO'), 0x14: ('Ermac', 'CONFIRMADO'), 0x16: ('Human Smoke', 'INFERIDO'),
    0x17: ('Noob Saibot', 'CONFIRMADO'), 0x18: ('Rain', 'CONFIRMADO'), 0x19: ('Idels', 'CONFIRMADO'),
    0x1A: ('Motaro', 'CONFIRMADO'), 0x1B: ('Shao Kahn', 'CONFIRMADO'),
}


def sha256_ok(data: bytes) -> bool:
    return hashlib.sha256(data).hexdigest() == ROM_SHA256


def _read(rom, cpu: int, length: int) -> bytes:
    ofs = cpu_to_file(cpu, rom.mapping)
    if ofs is None or ofs + length > len(rom.data):
        raise ValueError(f'Endereço ${cpu:06X} não está mapeado na ROM')
    return bytes(rom.data[ofs:ofs + length])


def read_tables(rom) -> dict:
    ids = _read(rom, ID_TABLE_CPU, ID_TABLE_LEN)
    nav = {k: _read(rom, cpu, ID_TABLE_LEN) for k, (cpu, _bit) in NAV_TABLES.items()}
    return {'ids': ids, 'nav': nav}


def resolve_character(cursor_index: int, ids: bytes, wram_1c59: int) -> int:
    """Replica $86:A1F6: tabela[índice]; se 0xFF usa o conteúdo de $7E:1C59."""
    if not 0 <= cursor_index < len(ids):
        raise IndexError(f'índice de cursor fora da tabela: {cursor_index:#x}')
    v = ids[cursor_index]
    return wram_1c59 & 0xFFFF if v == HIDDEN_MARK else v


def navigate(cursor_index: int, pad: int, nav: dict) -> int:
    """Próximo índice conforme as tabelas direcionais (prioridade do código: cima, baixo, esq., dir.).
    Não modela as condições especiais do índice 0x0A em $86:A726+ (ainda não reconstruídas)."""
    for key in ('up', 'down', 'left', 'right'):
        if pad & NAV_TABLES[key][1]:
            return nav[key][cursor_index]
    return cursor_index


def grid_rows(ids: bytes) -> list[list[int]]:
    """Layout deduzido das tabelas de navegação: linhas de 7, 7, 5 e 5 posições."""
    sizes, out, p = (7, 7, 5, 5), [], 0
    for n in sizes:
        out.append(list(ids[p:p + n])); p += n
    return out


_WRITE_ABS = {0x8D: 'STA', 0x8E: 'STX', 0x8C: 'STY', 0x9C: 'STZ', 0xEE: 'INC', 0xCE: 'DEC',
              0x0C: 'TSB', 0x1C: 'TRB', 0x0E: 'ASL', 0x4E: 'LSR', 0x2E: 'ROL', 0x6E: 'ROR'}
_WRITE_LONG = {0x8F: 'STA'}


def scan_wram_writes(data: bytes, wram_addr: int, mapping: str = 'exhirom') -> list[dict]:
    """Varredura por PADRÃO DE BYTES de escritas absolutas/longas ($7E) a um endereço WRAM.

    Limites: não decodifica instruções (podem ser falsos positivos em dados), não vê
    escritas indiretas, indexadas, por MVN/MVP ou DMA, e assume DB=$7E ou endereço < $2000.
    """
    out = []
    lo, hi = wram_addr & 0xFF, (wram_addr >> 8) & 0xFF
    for o in range(len(data) - 3):
        op = data[o]
        if op in _WRITE_ABS and data[o + 1] == lo and data[o + 2] == hi:
            kind = f'{_WRITE_ABS[op]} abs'
        elif op in _WRITE_LONG and data[o + 1] == lo and data[o + 2] == hi and data[o + 3] == 0x7E:
            kind = f'{_WRITE_LONG[op]} long $7E'
        else:
            continue
        out.append({'offset': o, 'cpu': file_to_cpu(o, mapping), 'kind': kind,
                    'bytes': data[o:o + 4].hex(' '), 'confidence': 'padrão de bytes (não verificado)'})
    return out
