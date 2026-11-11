"""Análise estática do slot especial 0x0A (quadro do Dragão) da seleção de personagens.

Somente leitura. Cada afirmação é ancorada em bytes da ROM (endereço CPU, offset de arquivo, bytes lidos).

Classes de evidência:
  ESTÁTICO-CONFIRMADO  bytes lidos da ROM e decodificados; nenhuma execução envolvida
  INFERIDO             dedução direta de fatos ESTÁTICO-CONFIRMADO
  HIPÓTESE             interpretação funcional não provada por execução
  NÃO VERIFICADO       não analisado, divergente ou sem evidência

Nada aqui prova comportamento em tempo de execução. Para isso existem os traces do Mesen
(backend/selection_probe.py e backend/decision_trace_diff.py).
"""
from __future__ import annotations
from collections import deque
from .core import cpu_to_file, file_to_cpu

ROM_SHA256 = 'f512ef861f0df2dbb8f9563fb5f3b01ab70b7048ac329a9262ff3d34ca487bdd'
DISPATCH_CPU = 0x86A726
DIRECTIONS = ('up', 'down', 'left', 'right')
# Bits do registrador padrão JOY1 ($4218/$4219): 11=Up 10=Down 9=Left 8=Right.
PAD_BIT = {'up': 0x0800, 'down': 0x0400, 'left': 0x0200, 'right': 0x0100}
ASL_AXIS = {0x1A: 'vertical', 0x16: 'horizontal'}   # ASL $1A dobra o passo Y do cursor; ASL $16 dobra o X
OK, UNVERIFIED = 'ESTÁTICO-CONFIRMADO', 'NÃO VERIFICADO'

# Esqueleto da rotina de despacho (118 bytes, $86:A726..A79B). '??' = operando livre.
_SKELETON = (
    '85 12 86 16 84 1A A9 ?? 00 85 14 A4 0E B7 12 29 FF 00 85 0E '
    'C9 ?? 00 D0 ?? AD 57 1C C9 ?? 00 D0 ?? AD A6 F5 F0 ?? 80 ?? A9 ?? 00 CD 50 3A F0 ?? CD 52 3A F0 ?? 4C ?? ?? '
    'A5 12 C9 ?? ?? D0 ?? 06 1A A9 ?? 00 85 0E 80 ?? '
    'A5 12 C9 ?? ?? D0 ?? 06 1A A9 ?? 00 85 0E 80 ?? '
    'A5 12 C9 ?? ?? D0 ?? 06 16 A9 ?? 00 85 0E 80 ?? '
    'A5 12 C9 ?? ?? D0 ?? 06 16 A9 ?? 00 85 0E')
SKELETON = tuple(None if t == '??' else int(t, 16) for t in _SKELETON.split())
assert len(SKELETON) == 0x76

# Deslocamentos relativos a $86:A726 (conferidos contra a desmontagem)
O_TABLE_BANK = 0x07            # A9 ?? 00  em A72C: banco das tabelas direcionais
O_SPECIAL = 0x15               # C9 ?? 00  em A73A: índice especial (0x0A)
O_SPECIAL_BNE = 0x17           # D0 5D     em A73D: se não for o especial, vai ao fim ($A79C = +0x76)
O_GATE_VALUE = 0x1D            # C9 ?? 00  em A742: valor de $1C57 que libera o especial
O_GATE_BNE = 0x1F              # D0 17     em A745: se $1C57 != gate, vai ao bloco de redirecionamento (+0x38)
O_STUBS = (0x24, 0x26, 0x2E, 0x33)   # F0 02 / 80 00 / F0 00 / F0 00: desvios cujos destinos convergem
O_BLOCKS = (0x38, 0x48, 0x58, 0x68)  # um bloco por direção: up, down, left, right
END_OF_ROUTINE = 0x76


def find_signature(data: bytes, pattern=SKELETON, limit: int = 16) -> list[int]:
    """Offsets de arquivo onde o padrão (com curingas) ocorre, independentemente do endereço CPU."""
    head = bytearray()
    for b in pattern:
        if b is None:
            break
        head.append(b)
    head = bytes(head)
    out, pos = [], 0
    while len(out) < limit:
        pos = data.find(head, pos)
        if pos < 0 or pos + len(pattern) > len(data):
            break
        if all(p is None or data[pos + i] == p for i, p in enumerate(pattern)):
            out.append(pos)
        pos += 1
    return out


def _cpu(c: int) -> str:
    return f'${c >> 16:02X}:{c & 0xFFFF:04X}'


def _rd(rom, cpu: int, n: int):
    o = cpu_to_file(cpu, rom.mapping)
    if o is None or o + n > len(rom.data):
        return None
    return bytes(rom.data[o:o + n])


def _fact(rom, fid: str, cpu: int, expect: str, text: str, cls: str = OK) -> dict:
    """Fato ancorado. `expect`: bytes hex com '??' (curinga). `verified` compara com a ROM lida."""
    exp = [None if t == '??' else int(t, 16) for t in expect.split()]
    b = _rd(rom, cpu, len(exp))
    ok = b is not None and all(e is None or e == x for e, x in zip(exp, b))
    return {'id': fid, 'cpu': _cpu(cpu), 'rom_offset': cpu_to_file(cpu, rom.mapping),
            'bytes': b.hex(' ') if b is not None else None, 'expected': expect, 'verified': ok,
            'class': cls if ok else UNVERIFIED, 'text': text}


def locate_dispatch(rom):
    """Offset de arquivo da rotina de despacho: endereço conhecido; senão, busca por assinatura."""
    o = cpu_to_file(DISPATCH_CPU, rom.mapping)
    if o is not None and find_signature(bytes(rom.data[o:o + len(SKELETON)])) == [0]:
        return o, 'endereço conhecido ($86:A726)'
    hits = find_signature(rom.data)
    if len(hits) == 1:
        return hits[0], 'assinatura (código possivelmente realocado)'
    return None, f'{len(hits)} ocorrências da assinatura'


def decode_dispatch(rom) -> dict:
    base, how = locate_dispatch(rom)
    if base is None:
        return {'found': False, 'reason': how}
    d = bytes(rom.data[base:base + len(SKELETON)])
    cpu0 = file_to_cpu(base, rom.mapping)

    def target(i: int) -> int:        # alvo, relativo ao início da rotina, do desvio de 2 bytes que começa em d[i]
        off = d[i + 1] - 256 if d[i + 1] > 127 else d[i + 1]
        return i + 2 + off

    redirects = {}
    for name, s in zip(DIRECTIONS, O_BLOCKS):
        redirects[name] = {'table_ptr': d[s + 3] | d[s + 4] << 8, 'target_index': d[s + 10],
                           'doubled_register': d[s + 8], 'axis': ASL_AXIS.get(d[s + 8], '?'), 'cpu': _cpu(cpu0 + s)}
    t = [target(o) for o in O_STUBS]
    # F0 02 salta o BRA seguinte e o BRA 00 vai ao mesmo ponto; os dois F0 00 caem na instrução seguinte.
    dead = t[0] == t[1] == O_STUBS[1] + 2 and t[2] == O_STUBS[2] + 2 and t[3] == O_STUBS[3] + 2
    return {'found': True, 'how_located': how, 'rom_offset': base, 'cpu': _cpu(cpu0),
            'table_bank': d[O_TABLE_BANK], 'special_index': d[O_SPECIAL], 'state_gate_value': d[O_GATE_VALUE],
            'special_miss_goes_to_end': target(O_SPECIAL_BNE) == END_OF_ROUTINE,
            'gate_miss_goes_to_redirects': target(O_GATE_BNE) == O_BLOCKS[0],
            'redirects': redirects, 'dead_branches_converge': dead,
            'dead_branch_targets': [f'+0x{x:02X}' for x in t]}


def read_tables(rom, dispatch: dict, slots: int = 24) -> dict:
    """Tabelas direcionais (próximo índice por índice atual) e tabela índice→ID. `slots` = nº de posições."""
    bank = dispatch['table_bank']
    nav = {}
    for name in DIRECTIONS:
        raw = _rd(rom, (bank << 16) | dispatch['redirects'][name]['table_ptr'], slots)
        if raw is None:
            raise ValueError(f'tabela {name} fora da ROM')
        nav[name] = raw
    ids = None
    head = _rd(rom, 0x86A1F6, 17)        # AA BF lo hi bank 29 FF 00 C9 FF 00 D0 03 AD 59 1C 6B
    if head and head[:2] == b'\xaa\xbf' and head[5:8] == b'\x29\xff\x00':
        ids = _rd(rom, head[4] << 16 | head[2] | head[3] << 8, slots)
    return {'nav': nav, 'ids': ids, 'hidden_marker': head[10] if head and len(head) > 10 else None}


def navigate(nav: dict, dispatch: dict, cur: int, direction: str, state: int) -> dict:
    """Reproduz $86:A726..A79B: índice seguinte para (índice atual, direção, valor de $1C57)."""
    nxt = nav[direction][cur]
    special = dispatch['special_index']
    if nxt != special:
        return {'next': nxt, 'redirected': False, 'step_scale': 1, 'via_special': False}
    if state == dispatch['state_gate_value']:
        return {'next': nxt, 'redirected': False, 'step_scale': 1, 'via_special': True}
    r = dispatch['redirects'][direction]
    return {'next': r['target_index'], 'redirected': True, 'step_scale': 2, 'axis': r['axis'], 'via_special': True}


def reachability(nav: dict, dispatch: dict, state: int, start: int = 0) -> dict:
    """Busca em largura a partir de `start`; lista índices alcançáveis e as entradas no índice especial."""
    seen, q, entries = {start}, deque([start]), []
    while q:
        c = q.popleft()
        for dname in DIRECTIONS:
            r = navigate(nav, dispatch, c, dname, state)
            if r['via_special']:
                entries.append({'from': c, 'direction': dname, 'lands_on': r['next'], 'redirected': r['redirected']})
            if r['next'] not in seen:
                seen.add(r['next'])
                q.append(r['next'])
    n = len(nav['up'])
    return {'state': state, 'reachable': sorted(seen), 'unreachable': sorted(set(range(n)) - seen), 'special_entries': entries}


def state_machine(rom) -> dict:
    """Todos os acessos válidos a $7E:1C57 (confirmados por bytes) e o grafo de estados que formam."""
    f = [
        _fact(rom, 'W1', 0x84A306, '9C 57 1C', 'STZ $1C57 (inicialização do processo da seleção): estado := 0'),
        _fact(rom, 'W2', 0x84A38E, '9C 57 1C', 'STZ $1C57 (entrada do processo "abrir"): estado := 0'),
        _fact(rom, 'W3', 0x84A398, 'A9 01 00 8D 57 1C', 'STA $1C57 com A=1 (após esperar $20 quadros): estado := 1'),
        _fact(rom, 'W4', 0x84A3F4, 'A9 02 00 8D 57 1C', 'STA $1C57 com A=2 (processo "fechar"): estado := 2'),
        _fact(rom, 'R1', 0x84A2A3, 'AD 57 1C D0 F4', 'processo do retrato: espera enquanto $1C57 != 0'),
        _fact(rom, 'R2', 0x84A2E2, 'AD 57 1C C9 02 00 D0 F1 80 B0', 'processo do retrato: aguarda $1C57 == 2 e volta ao início'),
        _fact(rom, 'R3', 0x84A3EC, 'AD 57 1C C9 01 00 D0 33', 'processo "fechar": só age se $1C57 == 1'),
        _fact(rom, 'R4', 0x86A73F, 'AD 57 1C C9 ?? 00 D0 ??', 'despacho do cursor: $1C57 == gate libera o índice especial'),
        _fact(rom, 'S1', 0x84A34C, 'F4 A3 84 F4 00 8D 48 22 B6 C7 88',
              'frame de pilha com retorno $84:A38D (+1 = $84:A38E): cria o processo "abrir"', 'INFERIDO'),
        _fact(rom, 'S2', 0x84A357, 'F4 A3 84 F4 00 EB 48 22 B6 C7 88',
              'frame de pilha com retorno $84:A3EB (+1 = $84:A3EC): cria o processo "fechar"', 'INFERIDO'),
    ]
    ok = all(x['verified'] for x in f if x['id'][0] in 'WR')
    return {'facts': f, 'all_access_points_verified': ok,
            'states': {0: 'retrato em repouso (processo do retrato pode redesenhar)', 1: 'quadro "aberto": cursor pode ocupar o slot',
                       2: 'quadro "fechando"'},
            'state_names_class': 'HIPÓTESE',
            'transitions': [{'to': 0, 'pc': '$84:A306', 'when': 'inicialização'},
                            {'to': 0, 'pc': '$84:A38E', 'when': 'início do processo "abrir"'},
                            {'to': 1, 'pc': '$84:A39B', 'when': 'depois de 0x20 quadros de espera'},
                            {'to': 2, 'pc': '$84:A3F7', 'when': 'processo "fechar", se estado == 1'}],
            'transitions_class': OK}


def portrait_chain(rom) -> dict:
    """Escolha do quadro do retrato em $84:A2B9..A2CF. Só $1C59 == 0x1B difere do padrão."""
    f = [_fact(rom, 'P1', 0x84A2AF, 'A9 70 00 85 22 A9 48 00 85 24', 'posição do retrato: x=$70, y=$48'),
         _fact(rom, 'P2', 0x84A2B9, 'AD 59 1C A2 02 00 C9 1B 00 F0 0B A2 00 00 C9 1A 00 F0 03 A2 00 00',
               'X:=2 se $1C59==$1B; senão X:=0 (também para $1A e para qualquer outro valor)'),
         _fact(rom, 'P3', 0x84A2CF, 'BF EC A2 84 A8 A9 06 04 22 50 A7 84', 'índice do quadro := tabela $84:A2EC[X]; desenha via $84:A750')]
    tab = _rd(rom, 0x84A2EC, 8)
    frames = [tab[i] | tab[i + 1] << 8 for i in range(0, 8, 2)] if tab else None
    ok = all(x['verified'] for x in f)
    return {'facts': f, 'frame_table': [f'{v:04X}' for v in frames] if frames else None,
            'selected_frames_by_id': {'0x1B': 2, 'qualquer outro ID (inclui 0x1A, 0x0B, 0x16, 0x19)': 0} if ok else None,
            'frames_never_selected_here': [4, 6] if ok else None, 'verified': ok}


def cycle_script(rom) -> dict:
    """Rodízio dos personagens ocultos: porta ($3BAE|$3BB0), Shao Kahn, Motaro e o bloco $FF:FE30."""
    f = [_fact(rom, 'C1', 0x84A328, 'AD AE 3B 0D B0 3B F0 55', 'porta do rodízio: ($3BAE | $3BB0) == 0 desvia para o repouso $84:A385'),
         _fact(rom, 'C2', 0x84A341, 'AD AE 3B F0 1C A9 1B 00 8D 59 1C', 'se $3BAE != 0: $1C59 := $1B (Shao Kahn)'),
         _fact(rom, 'C3', 0x84A362, 'AD B0 3B F0 ?? A9 1A 00 8D 59 1C', 'se $3BB0 != 0: $1C59 := $1A (Motaro)'),
         _fact(rom, 'C4', 0x84A37F, '5C 30 FE FF', 'JML $FF:FE30: continua no bloco de rodízio adicionado em espaço livre'),
         _fact(rom, 'C5', 0xFFFE3E, 'A9 0B 00 8D 59 1C', '$1C59 := $0B (Sheeva), incondicional'),
         _fact(rom, 'C6', 0xFFFE64, 'A9 16 00 8D 59 1C', '$1C59 := $16 (Human Smoke), incondicional'),
         _fact(rom, 'C7', 0xFFFE8A, 'A9 19 00 8D 59 1C', '$1C59 := $19, incondicional'),
         _fact(rom, 'C8', 0xFFFEA6, '5C 83 A3 C4', 'JML $C4:A383 (BRA $A330): volta ao início do rodízio'),
         _fact(rom, 'C9', 0x84A383, '80 AB', 'BRA $84:A330: espera $36C6 != 0 e reinicia a decisão')]
    gate = _rd(rom, 0x84A32E, 1)
    return {'facts': f, 'verified': all(x['verified'] for x in f),
            'gate_opcode': f'{gate[0]:02X}' if gate else None,
            'gate_mode': {0xF0: 'condicional (BEQ)', 0x80: 'FORÇADO (BRA): rodízio sempre desligado'}.get(gate[0]) if gate else None,
            'order_in_one_pass': [{'id': 0x1B, 'if': '$3BAE != 0'}, {'id': 0x1A, 'if': '$3BB0 != 0'},
                                  {'id': 0x0B, 'if': None}, {'id': 0x16, 'if': None}, {'id': 0x19, 'if': None}],
            'order_class': OK, 'order_note': 'ordem de um ciclo, lida do fluxo; a sequência observada 19→1B→1A→0B→16→19 coincide'}


def analyze(rom, slots: int = 24) -> dict:
    d = decode_dispatch(rom)
    out = {'dispatch': d}
    if d.get('found'):
        t = read_tables(rom, d, slots)
        out['tables'] = {'nav': {k: v.hex(' ') for k, v in t['nav'].items()},
                         'ids': t['ids'].hex(' ') if t['ids'] else None, 'hidden_marker': t['hidden_marker']}
        gate = d['state_gate_value']
        out['reachability'] = {'state_0': reachability(t['nav'], d, 0), f'state_{gate}': reachability(t['nav'], d, gate)}
        out['_nav'] = t['nav']
    out['state_1c57'] = state_machine(rom)
    out['portrait'] = portrait_chain(rom)
    out['cycle'] = cycle_script(rom)
    return out
