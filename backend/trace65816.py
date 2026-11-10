"""Parser de traces do Mesen para 65C816 (com separação de linhas SPC700).

Aceita linhas como::

    86A203 lda $1c59 [$7E1C59] = $001A A:0000 X:0003 Y:0000 S:01F3 D:0C00 DB:7E P:nvmxdIzc
    C086B1 inc $3bae [$7E3BAE] = $0000

Contrato de evidência
---------------------
* O valor após ``=`` é o conteúdo da memória **antes** da execução da instrução.
  Para ``STA/STZ/INC/...`` ele é o valor ANTERIOR, nunca o gravado.
* Registradores, quando presentes, são os valores antes da execução.
* Nada é inferido quando o trace não fornece o dado: campos ausentes ficam ``None``.
* O formato exato das tags de D/DB/P do Mesen 2 não está documentado de forma
  completa; os tokens são lidos por nome (``A:``, ``X:``, ``Y:``, ``S:``/``SP:``,
  ``D:``, ``DB:``, ``P:``) em qualquer ordem.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

MNEMONICS_65816 = frozenset('''adc and asl bcc bcs beq bit bmi bne bpl bra brk brl bvc bvs clc cld cli clv cmp cop cpx cpy dec dex
dey eor inc inx iny jml jmp jsl jsr lda ldx ldy lsr mvn mvp nop ora pea pei per pha phb phd phk php phx phy pla plb pld plp plx ply
rep rol ror rti rtl rts sbc sec sed sei sep sta stp stx sty stz tax tay tcd tcs tdc trb tsb tsc tsx txa txs txy tya tyx wai wdm xba xce'''.split())

BRANCHES = frozenset('bcc bcs beq bmi bne bpl bra bvc bvs brl'.split())
CONTROL = BRANCHES | frozenset('jmp jml jsr jsl rts rtl rti brk cop stp wai'.split())
CALLS = frozenset(('jsr', 'jsl'))
RETURNS = frozenset(('rts', 'rtl'))
READ_OPS = frozenset('lda ldx ldy cmp cpx cpy bit adc sbc and ora eor'.split())
WRITE_OPS = frozenset('sta stx sty stz'.split())
RMW_OPS = frozenset('inc dec asl lsr rol ror tsb trb'.split())
BLOCK_OPS = frozenset(('mvn', 'mvp'))
X_WIDTH_OPS = frozenset('ldx ldy cpx cpy stx sty'.split())

_H = r'([0-9A-Fa-f]{%d})'
_OPERAND_PATTERNS = [
    ('imp', r'^$'), ('acc', r'^a$'),
    ('imm', r'^#\$([0-9A-Fa-f]{2}|[0-9A-Fa-f]{4})$'),
    ('sr_iy', r'^\(\$' + _H % 2 + r',s\),y$'), ('sr', r'^\$' + _H % 2 + r',s$'),
    ('dpindx', r'^\(\$' + _H % 2 + r',x\)$'), ('dpindy', r'^\(\$' + _H % 2 + r'\),y$'),
    ('dpind', r'^\(\$' + _H % 2 + r'\)$'), ('dpindly', r'^\[\$' + _H % 2 + r'\],y$'),
    ('dpindl', r'^\[\$' + _H % 2 + r'\]$'),
    ('absindx', r'^\(\$' + _H % 4 + r',x\)$'), ('absind', r'^\(\$' + _H % 4 + r'\)$'),
    ('abslind', r'^\[\$' + _H % 4 + r'\]$'),
    ('longx', r'^\$' + _H % 6 + r',x$'), ('long', r'^\$' + _H % 6 + r'$'),
    ('absx', r'^\$' + _H % 4 + r',x$'), ('absy', r'^\$' + _H % 4 + r',y$'), ('abs', r'^\$' + _H % 4 + r'$'),
    ('dpx', r'^\$' + _H % 2 + r',x$'), ('dpy', r'^\$' + _H % 2 + r',y$'), ('dp', r'^\$' + _H % 2 + r'$'),
    ('block', r'^\$' + _H % 2 + r',\s*\$' + _H % 2 + r'$'),
]
_OPERAND_RE = [(m, re.compile(p)) for m, p in _OPERAND_PATTERNS]
_LEN = {'imp': 1, 'acc': 1, 'sr_iy': 2, 'sr': 2, 'dpindx': 2, 'dpindy': 2, 'dpind': 2, 'dpindly': 2, 'dpindl': 2,
        'dpx': 2, 'dpy': 2, 'dp': 2, 'absindx': 3, 'absind': 3, 'abslind': 3, 'absx': 3, 'absy': 3, 'abs': 3,
        'longx': 4, 'long': 4, 'block': 3}

LINE_RE = re.compile(
    r'^\s*(?:(?P<tag>\[(?:SPC700|SPC|S-SMP|SMP|CPU|SNES)\]|(?:SPC700|SPC|CPU)\s*:)\s*)?'
    r'(?P<pc>[0-9A-Fa-f]{4,6})\s+(?P<mn>[A-Za-z][A-Za-z0-9]{1,3})\b(?P<rest>.*)$')
REG_RE = re.compile(r'\b(?P<k>DB|PB|SP|A|X|Y|S|D|P)\s*[:=]\s*\$?(?P<v>[0-9A-Fa-f]{1,4}(?![A-Za-z])|[NnVvMmXxDdIiZzCcEe.\-]{8})(?![0-9A-Za-z])')
EA_RE = re.compile(r'\[\$(?P<ea>[0-9A-Fa-f]{6})\]')
VAL_RE = re.compile(r'=\s*\$(?P<val>[0-9A-Fa-f]{2}|[0-9A-Fa-f]{4})\b')
_FLAG_ORDER = 'NVMXDIZC'


@dataclass
class TraceLine:
    seq: int
    cpu: str                       # '65C816' | 'SPC700'
    cpu_basis: str                 # 'tag' | 'largura do PC' | 'mnemonico'
    pc: int
    mnemonic: str
    operand: str
    mode: str | None
    length: int | None
    ea: int | None = None          # endereço efetivo de 24 bits
    ea_basis: str | None = None    # 'trace' | 'calculado' | None
    mem_value: int | None = None   # valor ANTES da execução (conforme o trace)
    mem_digits: int | None = None
    regs: dict = field(default_factory=dict)
    flags: dict = field(default_factory=dict)
    raw: str = ''

    @property
    def text(self) -> str:
        return f'{self.mnemonic} {self.operand}'.strip()


def parse_flags(p) -> dict:
    """Aceita 'NvmxdIzC' (maiúscula = ligado), hexadecimal de 2 dígitos ou None."""
    if p is None:
        return {}
    if len(p) == 8 and not all(c in '0123456789abcdefABCDEF' for c in p):
        return {n.lower(): (c.isupper()) for n, c in zip(_FLAG_ORDER, p) if c not in '.-'} | \
               {n.lower(): None for n, c in zip(_FLAG_ORDER, p) if c in '.-'}
    try:
        v = int(p, 16)
    except ValueError:
        return {}
    if len(p) > 2:
        return {}
    return {n.lower(): bool(v & (0x80 >> i)) for i, n in enumerate(_FLAG_ORDER)}


def classify_operand(mn: str, operand: str):
    """Retorna (modo, valores) ou (None, ()) se o operando não for reconhecido."""
    op = operand.strip().lower()
    if mn in BRANCHES:
        m = re.match(r'^\$([0-9a-f]{4,6})$', op)
        return ('rel', (int(m.group(1), 16),)) if m else (None, ())
    for mode, rx in _OPERAND_RE:
        m = rx.match(op)
        if m:
            return mode, tuple(int(g, 16) for g in m.groups())
    return None, ()


def instruction_length(mn: str, mode, operand: str):
    if mode is None:
        return None
    if mode == 'rel':
        return 3 if mn == 'brl' else 2
    if mode == 'imm':
        return 1 + len(re.sub(r'[^0-9a-f]', '', operand.lower().split('$')[-1])) // 2
    return _LEN.get(mode)


def _hex(v):
    return int(v, 16)


def parse_line(text: str, seq: int) -> TraceLine | None:
    """Converte uma linha; devolve None se não for uma linha de instrução reconhecível."""
    if len(text) > 2000:
        return None
    m = LINE_RE.match(text)
    if not m:
        return None
    tag, pc_s, mn, rest = m.group('tag'), m.group('pc'), m.group('mn').lower(), m.group('rest')
    tag_l = (tag or '').lower()
    if 'spc' in tag_l or 'smp' in tag_l:
        cpu, basis = 'SPC700', 'tag'
    elif len(pc_s) == 6:
        if mn not in MNEMONICS_65816:
            return None
        cpu, basis = '65C816', 'tag' if tag else 'largura do PC'
    else:
        cpu, basis = 'SPC700', 'largura do PC'
    pc = _hex(pc_s)
    if cpu == 'SPC700':
        return TraceLine(seq, cpu, basis, pc, mn, rest.strip()[:80], None, None, raw=text[:200])
    regs = {}
    for r in REG_RE.finditer(rest):
        k = 'S' if r.group('k') == 'SP' else r.group('k')
        v = r.group('v')
        if k == 'P':
            regs['P'] = v
        elif re.fullmatch(r'[0-9A-Fa-f]{1,4}', v):
            regs[k] = _hex(v)
    body = REG_RE.sub('', rest)
    ea = None
    em = EA_RE.search(body)
    if em:
        ea = _hex(em.group('ea'))
        body = EA_RE.sub('', body, count=1)
    vm = VAL_RE.search(body)
    mem_value = mem_digits = None
    if vm:
        mem_value, mem_digits = _hex(vm.group('val')), len(vm.group('val'))
        body = VAL_RE.sub('', body, count=1)
    operand = body.strip()
    mode, vals = classify_operand(mn, operand)
    length = instruction_length(mn, mode, operand)
    flags = parse_flags(regs.get('P') if isinstance(regs.get('P'), str) else None)
    line = TraceLine(seq, cpu, basis, pc, mn, operand, mode, length, ea, 'trace' if ea is not None else None,
                     mem_value, mem_digits, dict(regs), flags, text[:200])
    if line.ea is None:
        _compute_ea(line, vals)
    return line


def _compute_ea(line: TraceLine, vals: tuple):
    """Endereço efetivo apenas para modos determinísticos com registradores presentes no trace."""
    r, mode, mn = line.regs, line.mode, line.mnemonic
    if mn in CONTROL or mn in ('pea', 'pei', 'per') or not vals:
        return
    ea = None
    if mode == 'abs' and 'DB' in r:
        ea = (r['DB'] << 16) | vals[0]
    elif mode in ('absx', 'absy') and 'DB' in r and ('X' if mode == 'absx' else 'Y') in r:
        ea = ((r['DB'] << 16) | vals[0]) + r['X' if mode == 'absx' else 'Y']
    elif mode == 'long':
        ea = vals[0]
    elif mode == 'longx' and 'X' in r:
        ea = vals[0] + r['X']
    elif mode == 'dp' and 'D' in r:
        ea = (r['D'] + vals[0]) & 0xFFFF
    elif mode in ('dpx', 'dpy') and 'D' in r and ('X' if mode == 'dpx' else 'Y') in r:
        ea = (r['D'] + vals[0] + r['X' if mode == 'dpx' else 'Y']) & 0xFFFF
    elif mode == 'sr' and 'S' in r:
        ea = (r['S'] + vals[0]) & 0xFFFF
    if ea is not None:
        line.ea, line.ea_basis = ea & 0xFFFFFF, 'calculado'


def wram_address(ea):
    """Endereço WRAM linear (0x00000–0x1FFFF) ou None. $00–$3F/$80–$BF:0000–1FFF espelham $7E:0000–1FFF."""
    if ea is None:
        return None
    bank, off = (ea >> 16) & 0xFF, ea & 0xFFFF
    if bank == 0x7E:
        return off
    if bank == 0x7F:
        return 0x10000 + off
    if (bank < 0x40 or 0x80 <= bank < 0xC0) and off < 0x2000:
        return off
    return None


def fmt_wram(w: int) -> str:
    return f'$7{"E" if w < 0x10000 else "F"}:{w & 0xFFFF:04X}'
