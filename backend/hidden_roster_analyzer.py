"""Hidden Roster Analyzer v2: timeline, máquina de estados e grafo a partir de traces do Mesen.

Política de evidência (ver docs/HIDDEN_ROSTER_ANALYZER.md):
  CONFIRMADO     valor visível no trace (leitura) ou valor gravado confirmado por leitura posterior
  DERIVADO       calculado de registradores/valores do trace (ex.: STA grava A); ainda sem leitura posterior
  INFERIDO       dedução de segunda ordem
  NÃO VERIFICADO dado ausente no trace; nenhum valor é inventado
O valor mostrado após '=' na linha de uma escrita é o valor ANTERIOR, nunca o gravado.
"""
from __future__ import annotations
import csv
import io
from collections import Counter, deque
from . import hidden_roster as hr
from .core import cpu_to_file, file_to_cpu, decode_one, CpuState, next_instruction_offset
from .trace65816 import (parse_line, wram_address, fmt_wram, TraceLine, classify_operand, CONTROL, BRANCHES,
                         CALLS, RETURNS, READ_OPS, WRITE_OPS, RMW_OPS, BLOCK_OPS, X_WIDTH_OPS)

DEFAULT_WATCH = {'1C59': 0x1C59, '3BAE': 0x3BAE, '3BB0': 0x3BB0, '3A50': 0x3A50, '36D0': 0x36D0, '52C8': 0x52C8}
WATCH_MEANING = {'1C59': 'ID do personagem oculto', '3BAE': 'condição investigada (Shao Kahn?)',
                 '3BB0': 'condição investigada (Motaro?)', '3A50': 'índice do cursor P1',
                 '36D0': 'ID resolvido', '52C8': 'ID sincronizado P1'}
# Escritores estáticos de $1C59 (docs/EVIDENCIAS.md E-005): PC canônico -> valor
STATIC_1C59_WRITERS = {0xC4A309: 0x00, 0xC4A349: 0x1B, 0xC4A36A: 0x1A, 0xFFFE41: 0x0B, 0xFFFE67: 0x16, 0xFFFE8D: 0x19}
KNOWN_IDS = bytes.fromhex('18 13 05 02 03 10 17 01 00 11 FF 15 04 09 07 0F 14 12 08 0A 06 0E 0D 0C')
RANK = {'NÃO VERIFICADO': 0, 'INFERIDO': 1, 'DERIVADO': 2, 'CONFIRMADO': 3}
LIMITATIONS = [
    'Um trace é uma amostra: não prova que caminhos ausentes nunca executam.',
    'Escritas sem endereço efetivo no trace (indiretas sem [$bbaaaa]), por DMA ou por SPC700 não são vistas.',
    'MVN/MVP: assume-se uma linha por iteração; se o log colapsa o bloco numa linha, o intervalo é estimado por A.',
    'Mesen: o valor após "=" é o conteúdo anterior à execução; o valor gravado só é CONFIRMADO por leitura posterior.',
    'Linhas SPC700 são identificadas pela etiqueta ou pela largura do PC (4 dígitos); não são decodificadas.',
    'Interrupções (NMI/IRQ) produzem descontinuidades que não se distinguem de linhas ausentes.',
    'D/DB só estão disponíveis se o formato do trace os incluir; sem eles, endereços calculados não são gerados.',
]


def canon_pc(pc: int) -> int:
    """PC canônico (espelhos $80–$BF -> $C0–$FF). Só colapsa quando o endereço mapeia para ROM ExHiROM."""
    f = cpu_to_file(pc, 'exhirom')
    c = file_to_cpu(f, 'exhirom') if f is not None else None
    return c if c is not None else pc


def _fmt_pc(pc: int) -> str:
    return f'${pc >> 16:02X}:{pc & 0xFFFF:04X}'


def character_name(var: str, value, ids: bytes):
    if value is None:
        return None
    if var in ('1C59', '36D0', '52C8'):
        c = hr.CHARACTERS.get(value)
        return c[0] if c else None
    if var == '3A50' and 0 <= value < len(ids):
        v = ids[value]
        if v == 0xFF:
            return 'slot oculto (ID via $7E:1C59)'
        c = hr.CHARACTERS.get(v)
        return c[0] if c else None
    return None


def _mask(width): return (1 << (8 * width)) - 1


def _rank_min(*labels):
    return min(labels, key=lambda x: RANK[x])


class _Analyzer:
    def __init__(self, watch, ids, max_events):
        self.watch = {k: v for k, v in watch.items()}
        self.ids = ids
        self.max_events = max_events
        self.watch_bytes = {}
        for name, a in self.watch.items():
            self.watch_bytes[a] = name
            self.watch_bytes[a + 1] = name
        self.shadow = {}
        self.events = []
        self.events_dropped = 0
        self.stats = Counter()
        self.mismatches = []
        self.discontinuities = []
        self.redirects = []
        self.malformed = []
        self.stack = []
        self.pending_return = None
        self.prev = None
        self.recent = deque(maxlen=4)
        self.entry = None
        self.pending_block = None
        self.blocks = {}
        self.edges = Counter()
        self.cur_block = None
        self.first_pc = self.last_pc = None
        self.indirect_unresolved = Counter()
        self._blk_seen = {}

    # ---- contexto -------------------------------------------------------------------------------------------------
    def _ctx(self):
        return {'pilha_de_chamadas': [_fmt_pc(canon_pc(f['call_pc'])) + '→' + _fmt_pc(canon_pc(f['target']))
                                      for f in self.stack[-3:]][::-1],
                'instrucoes_anteriores': list(self.recent)[-3:]}

    def _regs(self, ln: TraceLine):
        r = {k: (f'{v:04X}' if k != 'DB' else f'{v:02X}') for k, v in ln.regs.items() if k != 'P'}
        if 'P' in ln.regs:
            r['P'] = ln.regs['P']
        return r

    # ---- memória sombra --------------------------------------------------------------------------------------------
    def _observe(self, ln, w, nbytes, value):
        for i in range(nbytes):
            a, b = w + i, (value >> (8 * i)) & 0xFF
            if a > 0x1FFFF:
                break
            sh = self.shadow.get(a)
            if sh is not None:
                sb, evi = sh
                if sb != b:
                    self.stats['mismatch'] += 1
                    if len(self.mismatches) < 100:
                        self.mismatches.append({'seq': ln.seq, 'pc': _fmt_pc(ln.pc), 'address': fmt_wram(a),
                                                'esperado': f'{sb:02X}', 'observado': f'{b:02X}',
                                                'nota': 'valor mudou sem escrita visível no trace (DMA, escrita indireta, '
                                                        'linhas ausentes ou derivação incorreta)'})
                    self.shadow[a] = (b, None)
                    continue
                if evi is not None:
                    ev = self.events[evi]
                    ev['_pend'].discard(a)
                    if not ev['_pend'] and ev['confidence'] == 'DERIVADO':
                        ev['confidence'], ev['confirmed_by_seq'] = 'CONFIRMADO', ln.seq
                        ev['evidence'] = f'valor confirmado por leitura posterior (linha {ln.seq})'
            else:
                self.shadow[a] = (b, None)

    def _set(self, w, nbytes, value, evi):
        for i in range(nbytes):
            a = w + i
            if a > 0x1FFFF:
                break
            if value is None:
                self.shadow.pop(a, None)
            else:
                self.shadow[a] = ((value >> (8 * i)) & 0xFF, evi)

    def _word(self, a):
        lo, hi = self.shadow.get(a), self.shadow.get(a + 1)
        return None if lo is None or hi is None else lo[0] | hi[0] << 8

    def _emit(self, ln, w, nbytes, access, before, after, basis, conf, evidence, extra=None):
        names = sorted({self.watch_bytes[a] for a in range(w, w + max(nbytes, 1)) if a in self.watch_bytes})
        if not names:
            return None
        self.stats['events'] += 1
        if len(self.events) >= self.max_events:
            self.events_dropped += 1
            return None
        ev = {'n': len(self.events), 'seq': ln.seq, 'pc': _fmt_pc(ln.pc), 'pc_canon': _fmt_pc(canon_pc(ln.pc)),
              'instruction': ln.text, 'access': access, 'address': fmt_wram(w), 'size': nbytes or None,
              'vars': names, 'meaning': [WATCH_MEANING.get(n, 'variável monitorada') for n in names],
              'value_before': before, 'value_after': after, 'after_basis': basis,
              'address_basis': ln.ea_basis, 'registers': self._regs(ln), 'context': self._ctx(),
              'confidence': conf, 'evidence': evidence, 'character': None, 'confirmed_by_seq': None,
              '_pend': set()}
        if extra:
            ev.update(extra)
        main = names[0]
        shown = after if after is not None else before
        ev['character'] = character_name(main, shown, self.ids)
        self.events.append(ev)
        return len(self.events) - 1

    # ---- acessos de memória ----------------------------------------------------------------------------------------
    @staticmethod
    def _width(ln):
        f = ln.flags.get('x' if ln.mnemonic in X_WIDTH_OPS else 'm')
        if f is True:
            return 1
        if f is False:
            return 2
        return ln.mem_digits // 2 if ln.mem_digits else None

    def _memory_access(self, ln):
        mn = ln.mnemonic
        if ln.mode in ('imm', 'imp', 'acc', None) or mn not in READ_OPS | WRITE_OPS | RMW_OPS:
            return
        if ln.ea is None:
            if ln.mode and ('ind' in ln.mode or ln.mode == 'sr_iy'):
                self.indirect_unresolved[_fmt_pc(canon_pc(ln.pc))] += 1
                self.stats['indirect_unresolved'] += 1
            return
        w = wram_address(ln.ea)
        if w is None:
            return
        width = self._width(ln)
        nb = width or 2
        obs = ln.mem_value
        if obs is not None:
            self._observe(ln, w, ln.mem_digits // 2, obs)
        basis_conf = 'CONFIRMADO' if ln.ea_basis == 'trace' else 'DERIVADO'
        if mn in READ_OPS:
            self.stats['wram_reads'] += 1
            if obs is None:
                self._emit(ln, w, width or 0, 'read', None, None, 'sem valor no trace', 'NÃO VERIFICADO',
                           'o trace não mostra o valor lido')
            else:
                self._emit(ln, w, ln.mem_digits // 2, 'read', obs, None, 'valor lido (conteúdo exibido pelo trace)',
                           basis_conf, 'leitura exibida pelo trace')
            return
        # escrita / leitura-modificação-escrita
        self.stats['wram_writes'] += 1
        r, a_reg = ln.regs, ln.regs.get('A')
        after = None
        why = ''
        if width is None:
            why = 'largura do acesso desconhecida (sem P e sem valor exibido)'
        elif mn == 'sta':
            after, why = (a_reg & _mask(width), 'STA grava A (A do trace)') if a_reg is not None else (None, 'A ausente no trace')
        elif mn == 'stx':
            after, why = (r['X'] & _mask(width), 'STX grava X') if 'X' in r else (None, 'X ausente no trace')
        elif mn == 'sty':
            after, why = (r['Y'] & _mask(width), 'STY grava Y') if 'Y' in r else (None, 'Y ausente no trace')
        elif mn == 'stz':
            after, why = 0, 'STZ grava zero'
        elif obs is None:
            why = 'valor anterior ausente: não é possível derivar o resultado'
        else:
            m = _mask(width)
            c = ln.flags.get('c')
            if mn == 'inc': after, why = (obs + 1) & m, 'INC: anterior + 1'
            elif mn == 'dec': after, why = (obs - 1) & m, 'DEC: anterior - 1'
            elif mn == 'asl': after, why = (obs << 1) & m, 'ASL'
            elif mn == 'lsr': after, why = obs >> 1, 'LSR'
            elif mn == 'rol' and c is not None: after, why = ((obs << 1) | int(c)) & m, 'ROL com C do trace'
            elif mn == 'ror' and c is not None: after, why = (obs >> 1) | (int(c) << (8 * width - 1)), 'ROR com C do trace'
            elif mn == 'tsb' and a_reg is not None: after, why = obs | (a_reg & m), 'TSB: anterior | A'
            elif mn == 'trb' and a_reg is not None: after, why = obs & ~a_reg & m, 'TRB: anterior & ~A'
            else: why = 'operação sem dados suficientes (A ou C ausente)'
        access = 'write' if mn in WRITE_OPS else 'rmw'
        conf = _rank_min(basis_conf, 'DERIVADO') if after is not None else 'NÃO VERIFICADO'
        evi = self._emit(ln, w, width or 0, access, obs, after,
                         'derivado dos registradores do trace' if after is not None else 'desconhecido',
                         conf, why + ('; aguardando leitura posterior' if after is not None else ''))
        if evi is not None and after is not None:
            self.events[evi]['_pend'] = {w + i for i in range(width)}
        self._set(w, nb, after if width else None, evi if after is not None else None)
        if evi is not None:
            ev = self.events[evi]
            ev['word_after'] = {n: self._word(self.watch[n]) for n in ev['vars']}
            ev['partial'] = not (width == 2 and all(self.watch[n] == w for n in ev['vars']))

    # ---- MVN/MVP ---------------------------------------------------------------------------------------------------
    def _block_apply(self, bl, count, collapsed, truncated):
        ln = bl
        _, vals = classify_operand(ln.mnemonic, ln.operand)
        if len(vals) != 2 or 'X' not in ln.regs or 'Y' not in ln.regs:
            self.stats['block_without_regs'] += 1
            return
        src_bank, dst_bank = vals  # ordem do assembler: origem, destino (HIPÓTESE sobre o formato do Mesen)
        x, y = ln.regs['X'], ln.regs['Y']
        step = 1 if ln.mnemonic == 'mvn' else -1
        for i in range(count):
            s = wram_address((src_bank << 16) | ((x + step * i) & 0xFFFF))
            d = wram_address((dst_bank << 16) | ((y + step * i) & 0xFFFF))
            if d is None:
                continue
            sh = self.shadow.get(s) if s is not None else None
            val = sh[0] if sh else None
            if val is None:
                self.shadow.pop(d, None)
            else:
                self.shadow[d] = (val, None)
            if d in self.watch_bytes:
                key = (ln.seq, self.watch_bytes[d])
                prev_evi = self._blk_seen.get(key)
                if prev_evi is not None:
                    ev = self.events[prev_evi]
                    ev['size'] = 2
                    ev['value_after'] = self._word(self.watch[self.watch_bytes[d]])
                    self.stats['block_bytes'] += 1
                    continue
                self._blk_seen[key] = self._emit(ln, d, 1, 'block_move', None, val,
                           'cópia de origem conhecida (memória sombra)' if val is not None else 'origem desconhecida',
                           'DERIVADO' if val is not None else 'NÃO VERIFICADO',
                           f'{ln.mnemonic.upper()} ${src_bank:02X},${dst_bank:02X}: '
                           f'{fmt_wram(s) if s is not None else "origem fora da WRAM"} → {fmt_wram(d)}'
                           + ('; bloco colapsado em uma linha (extensão estimada por A)' if collapsed else '')
                           + ('; trace truncado no meio do bloco' if truncated else ''),
                           {'partial': True})
            self.stats['block_bytes'] += 1

    def _flush_block(self, nxt: TraceLine | None):
        bl = self.pending_block
        if bl is None:
            return
        self.pending_block = None
        a = bl.regs.get('A')
        if nxt is not None and nxt.pc == bl.pc and nxt.mnemonic == bl.mnemonic:
            self._block_apply(bl, 1, False, False)
        elif nxt is not None and nxt.pc == ((bl.pc & 0xFF0000) | ((bl.pc + 3) & 0xFFFF)):
            if a is not None and a != 0 and a != 0xFFFF:
                self._block_apply(bl, min(a + 1, 0x20000), True, False)
            else:
                self._block_apply(bl, 1, False, False)
        else:
            self._block_apply(bl, 1, False, True)

    # ---- fluxo -----------------------------------------------------------------------------------------------------
    def feed(self, ln: TraceLine):
        self.stats['cpu_lines'] += 1
        if self.first_pc is None:
            self.first_pc = ln.pc
        self.last_pc = ln.pc
        if self.pending_block is not None:
            self._flush_block(ln)
        # continuidade e retornos
        pl = self.prev
        if self.pending_return is not None:
            exp = self.pending_return
            self.pending_return = None
            if canon_pc(ln.pc) != canon_pc(exp['to']):
                self.stats['return_redirect'] += 1
                if len(self.redirects) < 100:
                    self.redirects.append({'seq': ln.seq, 'retorno_em': _fmt_pc(exp['at']), 'esperado': _fmt_pc(exp['to']),
                                           'executado': _fmt_pc(ln.pc),
                                           'nota': 'retorno não voltou ao ponto da chamada (pilha alterada: HIPÓTESE de '
                                                   'redirecionamento, ou chamada fora do trace)'})
        starts_block = pl is None
        if pl is not None:
            exp_pc = (pl.pc & 0xFF0000) | ((pl.pc + pl.length) & 0xFFFF) if pl.length else None
            sequential = exp_pc is not None and ln.pc == exp_pc and pl.mnemonic not in CONTROL
            if pl.mnemonic not in CONTROL and exp_pc is not None and ln.pc != exp_pc:
                self.stats['discontinuity'] += 1
                if len(self.discontinuities) < 100:
                    self.discontinuities.append({'seq': ln.seq, 'apos': _fmt_pc(pl.pc), 'esperado': _fmt_pc(exp_pc),
                                                 'visto': _fmt_pc(ln.pc),
                                                 'nota': 'linhas ausentes, NMI/IRQ ou fluxo alterado fora do trace'})
            if not sequential or pl.mnemonic in CONTROL:
                starts_block = True
        if starts_block:
            self._new_block(ln, pl)
        self._count_block(ln)
        # instrução atual
        mn = ln.mnemonic
        if mn in BLOCK_OPS:
            self.pending_block = ln
        elif ln.mode is None:
            self.stats['unparsed_operand'] += 1
        else:
            self._memory_access(ln)
        if mn in CALLS and ln.length:
            _, vals = classify_operand(mn, ln.operand)
            tgt = (vals[0] if mn == 'jsl' else (ln.pc & 0xFF0000) | vals[0]) if vals else ln.pc
            self.stack.append({'call_pc': ln.pc, 'target': tgt,
                               'ret': (ln.pc & 0xFF0000) | ((ln.pc + ln.length) & 0xFFFF)})
            if len(self.stack) > 256:
                self.stack.pop(0)
        elif mn in RETURNS:
            if self.stack:
                f = self.stack.pop()
                self.pending_return = {'at': ln.pc, 'to': f['ret']}
            else:
                self.stats['unmatched_return'] += 1
        self.recent.append(f'{_fmt_pc(ln.pc)} {ln.text}')
        self.prev = ln

    def _new_block(self, ln, pl):
        start = canon_pc(ln.pc)
        if len(self.blocks) < 20000 or start in self.blocks:
            b = self.blocks.setdefault(start, {'start': start, 'n': 0, 'last_pc': ln.pc, 'last_mn': ln.mnemonic,
                                               'flags': dict(ln.flags)})
            if pl is not None and self.cur_block is not None:
                self.edges[(self.cur_block, start)] += 1
            self.cur_block = start
        else:
            self.stats['blocks_capped'] += 1

    def _count_block(self, ln):
        b = self.blocks.get(self.cur_block)
        if b is not None:
            b['n'] += 1
            b['last_pc'], b['last_mn'] = ln.pc, ln.mnemonic
            if ln.flags:
                b['flags'] = dict(ln.flags)

    def finish(self):
        self._flush_block(None)


def _roster(events, ids):
    """Transições de $1C59 comprovadas por escritas do trace."""
    seq, last_val, gates = [], None, {}
    for ev in events:
        if '3BAE' in ev['vars'] or '3BB0' in ev['vars']:
            if ev['access'] == 'read' and ev['value_before'] is not None:
                for n in ev['vars']:
                    if n in ('3BAE', '3BB0'):
                        gates[n] = {'valor': ev['value_before'], 'seq': ev['seq'], 'pc': ev['pc']}
        if '1C59' not in ev['vars'] or ev['access'] == 'read':
            continue
        if ev['access'] == 'block_move':
            seq.append({'seq': ev['seq'], 'pc': ev['pc'], 'pc_canon': ev['pc_canon'], 'instruction': ev['instruction'],
                        'value': ev['value_after'], 'name': None, 'origin': 'MVN (limpeza/cópia em bloco)',
                        'consistent_with_static': None, 'writer_known_statically': False, 'repeats_previous': False,
                        'confidence': ev['confidence'], 'event': ev['n'], 'gates_observed': dict(gates),
                        'static_expected_value': None, 'previous': None})
            continue
        v = ev['value_after']
        pcv = int(ev['pc_canon'].replace('$', '').replace(':', ''), 16)
        exp = STATIC_1C59_WRITERS.get(pcv)
        entry = {'seq': ev['seq'], 'pc': ev['pc'], 'pc_canon': ev['pc_canon'], 'instruction': ev['instruction'],
                 'value': v, 'name': character_name('1C59', v, ids), 'previous': ev['value_before'],
                 'static_expected_value': exp,
                 'consistent_with_static': (None if exp is None or v is None else exp == v),
                 'writer_known_statically': exp is not None, 'gates_observed': dict(gates),
                 'confidence': ev['confidence'], 'event': ev['n']}
        entry['repeats_previous'] = (v is not None and v == last_val)
        if v is not None:
            last_val = v
        seq.append(entry)
    changes = [e for e in seq if e['value'] is not None and not e['repeats_previous'] and 'origin' not in e]
    return {'writes': seq, 'sequence': [(e['value'], e['name']) for e in changes],
            'note': 'Sequência observada NESTE trace; não é a ordem universal do jogo. Só inclui escritas visíveis.'}


def _graph(az: _Analyzer, rom=None):
    blocks = az.blocks
    nodes = [{'id': _fmt_pc(b['start']), 'start': b['start'], 'instructions': b['n'], 'last': b['last_mn'],
              'evidence': 'EXECUTADO (trace)'} for b in blocks.values()]
    edges = [{'from': _fmt_pc(a), 'to': _fmt_pc(b), 'count': c, 'evidence': 'EXECUTADO (trace)'}
             for (a, b), c in az.edges.items()]
    if rom is not None:
        executed = {(a, b) for (a, b) in az.edges}
        for b in list(blocks.values())[:2000]:
            f = cpu_to_file(b['last_pc'], rom.mapping)
            fl = b['flags']
            if f is None or f >= len(rom.data):
                continue
            st = CpuState(False, fl.get('m', True), fl.get('x', True)) if fl else CpuState(False, True, True)
            ins = decode_one(rom.data, f, st, rom.mapping)
            if not ins or ins['size'] is None:
                continue
            cands = []
            if ins['target'] is not None and ins['flow'] in ('branch', 'jump', 'call'):
                cands.append(canon_pc(ins['target']))
            if ins['flow'] in ('branch', 'call'):
                nx = next_instruction_offset(f, ins['size'], rom.mapping)
                if nx is not None:
                    c = file_to_cpu(nx, rom.mapping)
                    if c is not None:
                        cands.append(canon_pc(c))
            for t in cands:
                if (b['start'], t) in executed:
                    for e in edges:
                        if e['from'] == _fmt_pc(b['start']) and e['to'] == _fmt_pc(t):
                            e['evidence'] = 'EXECUTADO + ESTÁTICO'
                else:
                    edges.append({'from': _fmt_pc(b['start']), 'to': _fmt_pc(t), 'count': 0,
                                  'evidence': 'INFERIDO (estático, não observado)'})
    return {'nodes': nodes, 'edges': edges, 'truncated': az.stats.get('blocks_capped', 0) > 0,
            'note': 'Aresta EXECUTADA = vista no trace. INFERIDA = decorre da decodificação da ROM e não foi observada.'}


def analyze_lines(lines, watch=None, ids=None, rom=None, max_events=50000, tail_incomplete=False):
    watch = watch or DEFAULT_WATCH
    if rom is not None and ids is None:
        try:
            ids = hr.read_tables(rom)['ids']
        except ValueError:
            ids = None
    ids = ids or KNOWN_IDS
    az = _Analyzer(watch, ids, max_events)
    total = 0
    last_raw = ''
    for total, text in enumerate(lines, 1):
        last_raw = text
        if not text.strip():
            az.stats['blank'] += 1
            continue
        if text.lstrip().startswith('#'):
            az.stats['comments'] += 1
            continue
        ln = parse_line(text, total)
        if ln is None:
            az.stats['malformed'] += 1
            if len(az.malformed) < 20:
                az.malformed.append({'seq': total, 'text': text[:120]})
            continue
        if ln.cpu == 'SPC700':
            az.stats['spc700_lines'] += 1
            continue
        az.feed(ln)
    az.finish()
    st = az.stats
    notes = []
    if tail_incomplete and last_raw:
        notes.append('O arquivo não termina com quebra de linha: a última linha pode estar cortada '
                     '(uma linha cortada pode continuar válida, por exemplo "sta $1c").')
    if st['cpu_lines'] and total >= 10000 and total % 10000 == 0:
        notes.append(f'{total} linhas é um número redondo: possível limite do buffer do Trace Logger; '
                     'não assuma que o trace cobre toda a execução.')
    if st['unmatched_return']:
        notes.append(f'{st["unmatched_return"]} retorno(s) sem chamada no trace: o início provavelmente está no meio de uma rotina.')
    if st['discontinuity']:
        notes.append(f'{st["discontinuity"]} descontinuidade(s) de PC: há linhas ausentes, interrupções ou fluxo alterado.')
    if st['malformed'] > 0:
        notes.append(f'{st["malformed"]} linha(s) ignorada(s) por formato desconhecido.')
    if st['cpu_lines'] == 0:
        notes.append('Nenhuma instrução 65C816 reconhecida.')
    events = [{k: v for k, v in e.items() if not k.startswith('_')} for e in az.events]
    per_var = {}
    for n, a in az.watch.items():
        evs = [e for e in events if n in e['vars']]
        per_var[n] = {'address': fmt_wram(a), 'meaning': WATCH_MEANING.get(n, ''),
                      'events': len(evs), 'writes': sum(e['access'] != 'read' for e in evs),
                      'reads': sum(e['access'] == 'read' for e in evs),
                      'distinct_values_after': sorted({e['value_after'] for e in evs if e['value_after'] is not None}),
                      'first_seq': evs[0]['seq'] if evs else None}
    return {
        'meta': {'lines_total': total, 'cpu_lines': st['cpu_lines'], 'spc700_lines': st['spc700_lines'],
                 'malformed_lines': st['malformed'], 'blank_lines': st['blank'], 'events': st['events'],
                 'events_returned': len(events), 'events_dropped': az.events_dropped,
                 'wram_reads': st['wram_reads'], 'wram_writes': st['wram_writes'], 'block_bytes_modeled': st['block_bytes'],
                 'memory_mismatches': st['mismatch'], 'indirect_without_effective_address': st['indirect_unresolved'],
                 'return_redirects': st['return_redirect'], 'discontinuities': st['discontinuity'],
                 'first_pc': _fmt_pc(az.first_pc) if az.first_pc is not None else None,
                 'last_pc': _fmt_pc(az.last_pc) if az.last_pc is not None else None,
                 'truncation_notes': notes,
                 'evidence_policy': 'O valor após "=" é anterior à execução. Valor gravado: DERIVADO dos registradores; '
                                    'CONFIRMADO só após leitura posterior coincidente.'},
        'events': events, 'summary': per_var, 'roster': _roster(events, ids),
        'anomalies': {'memory_mismatches': az.mismatches, 'discontinuities': az.discontinuities,
                      'return_redirects': az.redirects, 'malformed_samples': az.malformed,
                      'indirect_sites': dict(az.indirect_unresolved.most_common(20))},
        'graph': _graph(az, rom), 'limitations': LIMITATIONS,
    }


def analyze_bytes(raw: bytes, **kw):
    if len(raw) > 128 * 1024 * 1024:
        raise ValueError('Trace acima de 128 MiB')
    text = raw.decode('utf-8-sig', errors='replace')
    tail = bool(raw) and not raw.endswith(b'\n')
    return analyze_lines(text.splitlines(), tail_incomplete=tail, **kw)


EVENT_COLUMNS = ['n', 'seq', 'pc', 'pc_canon', 'instruction', 'access', 'address', 'vars', 'value_before', 'value_after',
                 'after_basis', 'confidence', 'character', 'evidence', 'registers', 'context']


def events_to_csv(events) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(EVENT_COLUMNS)
    for e in events:
        row = []
        for c in EVENT_COLUMNS:
            v = e.get(c)
            if c in ('value_before', 'value_after') and v is not None:
                v = f'0x{v:04X}' if v > 0xFF else f'0x{v:02X}'
            elif isinstance(v, (list, dict)):
                v = '; '.join(f'{k}={x}' for k, x in v.items()) if isinstance(v, dict) else ','.join(map(str, v))
            row.append('' if v is None else v)
        w.writerow(row)
    return buf.getvalue()


def filter_events(events, var=None, character=None, access=None, min_confidence=None):
    """Filtros usados pela API/UI e pelas exportações."""
    out = []
    mc = RANK.get(min_confidence) if min_confidence else None
    for e in events:
        if var and var.upper().replace('$7E:', '') not in e['vars']:
            continue
        if character and character.lower() not in (e.get('character') or '').lower():
            continue
        if access and e['access'] != access:
            continue
        if mc is not None and RANK[e['confidence']] < mc:
            continue
        out.append(e)
    return out
