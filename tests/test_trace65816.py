"""Parser 65C816 + Hidden Roster Analyzer v2. Não depende de FastAPI nem da ROM."""
import os
from pathlib import Path
import pytest
from backend.trace65816 import parse_line, parse_flags, wram_address, fmt_wram
from backend.hidden_roster_analyzer import (analyze_lines, analyze_bytes, events_to_csv, filter_events, canon_pc)
from backend.core import Rom

P16 = 'nvmxdIzc'      # M=0, X=0 (16 bits)
P8 = 'nvMXdIzc'       # M=1, X=1 (8 bits)


def L(pc, asm, ea=None, val=None, A=0, X=0, Y=0, S=0x01F3, D=0, DB=0x7E, P=P16, width=4):
    mid = (f' [${ea:06X}]' if ea is not None else '') + (f' = ${val:0{width}X}' if val is not None else '')
    return f'{pc:06X} {asm}{mid} A:{A:04X} X:{X:04X} Y:{Y:04X} S:{S:04X} D:{D:04X} DB:{DB:02X} P:{P}'


def run(lines, **kw):
    return analyze_lines(lines if isinstance(lines, list) else lines.splitlines(), **kw)


# ---- parsing --------------------------------------------------------------------------------------------------
def test_parse_prompt_sample_lines():
    a = parse_line('86A1F6 tax', 1)
    assert (a.pc, a.mnemonic, a.cpu, a.length) == (0x86A1F6, 'tax', '65C816', 1)
    b = parse_line('86A1F7 lda $86a207,x', 2)
    assert b.mode == 'longx' and b.length == 4
    c = parse_line('86A203 lda $1c59 [$7E1C59] = $001A', 3)
    assert c.ea == 0x7E1C59 and c.ea_basis == 'trace' and c.mem_value == 0x1A and c.mem_digits == 4
    assert parse_line('86A206 rtl', 4).mnemonic == 'rtl'


def test_parse_registers_and_flags():
    ln = parse_line(L(0x86A203, 'lda $1c59', ea=0x7E1C59, val=0x1A, A=0x1234, X=3, Y=4, S=0x01F3, D=0x0C00, DB=0x7E), 1)
    assert ln.regs['A'] == 0x1234 and ln.regs['X'] == 3 and ln.regs['Y'] == 4
    assert ln.regs['S'] == 0x01F3 and ln.regs['D'] == 0x0C00 and ln.regs['DB'] == 0x7E
    assert ln.flags['m'] is False and ln.flags['x'] is False and ln.flags['i'] is True
    assert parse_flags('30')['m'] is True and parse_flags('30')['x'] is True and parse_flags('30')['c'] is False
    assert parse_flags('zz') == {} and parse_flags(None) == {}


def test_immediate_width_drives_length():
    assert parse_line('C4A346 lda #$001b', 1).length == 3
    assert parse_line('C4A346 lda #$1b', 1).length == 2
    assert parse_line('C4A34C pea $84a3', 1).length == 3
    assert parse_line('C083FF mvn $7e,$7e', 1).length == 3


def test_wram_mirrors_and_24bit():
    assert wram_address(0x7E1C59) == wram_address(0x001C59) == wram_address(0x801C59) == 0x1C59
    assert wram_address(0x7F0010) == 0x10010 and fmt_wram(0x10010) == '$7F:0010'
    assert wram_address(0xC01C59) is None and wram_address(0x002100) is None and wram_address(0x003BAE) is None
    assert canon_pc(0x86A1F6) == canon_pc(0xC6A1F6) == 0xC6A1F6


# ---- 8/16 bits e valor anterior vs gravado ----------------------------------------------------------------------
def test_16bit_vs_8bit_store():
    r = run([L(0x808000, 'sta $1c59', ea=0x7E1C59, val=0x0000, A=0x1234, P=P16)])
    assert r['events'][0]['value_after'] == 0x1234 and r['events'][0]['size'] == 2
    r = run([L(0x808000, 'sta $1c59', ea=0x7E1C59, val=0x00, A=0x1234, P=P8, width=2)])
    assert r['events'][0]['value_after'] == 0x34 and r['events'][0]['size'] == 1


def test_value_shown_on_store_is_previous_not_written():
    r = run([L(0xC4A349, 'sta $1c59', ea=0x7E1C59, val=0x001A, A=0x001B)])
    e = r['events'][0]
    assert e['value_before'] == 0x1A and e['value_after'] == 0x1B
    assert e['confidence'] == 'DERIVADO' and e['access'] == 'write'


def test_no_register_no_value():
    line = '86A349 sta $1c59 [$7E1C59] = $001A'          # sem A e sem P: nada pode ser derivado
    e = run([line])['events'][0]
    assert e['value_after'] is None and e['confidence'] == 'NÃO VERIFICADO'


def test_confirmation_by_later_read_and_mismatch():
    ok = run([L(0x808000, 'sta $1c59', ea=0x7E1C59, val=0, A=0x001B),
              L(0x808003, 'lda $1c59', ea=0x7E1C59, val=0x001B)])
    assert ok['events'][0]['confidence'] == 'CONFIRMADO' and ok['events'][0]['confirmed_by_seq'] == 2
    bad = run([L(0x808000, 'sta $1c59', ea=0x7E1C59, val=0, A=0x001B),
               L(0x808003, 'lda $1c59', ea=0x7E1C59, val=0x0099)])
    assert bad['events'][0]['confidence'] == 'DERIVADO' and bad['meta']['memory_mismatches'] >= 1
    assert bad['anomalies']['memory_mismatches'][0]['address'] == '$7E:1C59'


def test_rmw_and_stz():
    r = run([L(0x808000, 'inc $3bae', ea=0x7E3BAE, val=0x0000),
             L(0x808003, 'dec $3bb0', ea=0x7E3BB0, val=0x0005),
             L(0x808006, 'stz $3a50', ea=0x7E3A50, val=0x0003),
             L(0x808009, 'asl $36d0', ea=0x7E36D0, val=0x0003),
             L(0x80800C, 'tsb $52c8', ea=0x7E52C8, val=0x00F0, A=0x000F)])
    after = [e['value_after'] for e in r['events']]
    assert after == [1, 4, 0, 6, 0xFF]
    assert [e['access'] for e in r['events']] == ['rmw', 'rmw', 'write', 'rmw', 'rmw']


def test_rmw_without_previous_value_is_unknown():
    e = run(['808000 inc $3bae [$7E3BAE] A:0000 P:nvmxdIzc'])['events'][0]
    assert e['value_after'] is None and e['confidence'] == 'NÃO VERIFICADO'


# ---- endereçamento -------------------------------------------------------------------------------------------
def test_indirect_with_and_without_effective_address():
    r = run([L(0x86A7A8, 'sta ($94)', ea=0x7E3A50, val=0x0003, A=0x000A, D=0x0C00)])
    assert r['events'][0]['vars'] == ['3A50'] and r['events'][0]['value_after'] == 0x0A
    r = run(['86A7A8 sta ($94) A:000A X:0000 Y:0000 S:01F3 D:0C00 DB:7E P:nvmxdIzc'])
    assert r['events'] == [] and r['meta']['indirect_without_effective_address'] == 1


def test_direct_page_and_computed_address_basis():
    r = run([L(0x808000, 'sta $0e', A=0x0007, D=0x0C00)], watch={'T': 0x0C0E})
    e = r['events'][0]
    assert e['address'] == '$7E:0C0E' and e['address_basis'] == 'calculado' and e['value_after'] == 7
    r = run([L(0x808000, 'sta $0e', A=0x0007, D=0x0C00)], watch={'T': 0x0C0E})
    assert r['events'][0]['confidence'] == 'DERIVADO'
    # sem D no trace, nenhum endereço é inventado
    assert run(['808000 sta $0e A:0007 P:nvmxdIzc'], watch={'T': 0x0C0E})['events'] == []


# ---- MVN / MVP -------------------------------------------------------------------------------------------------
def test_mvn_one_line_per_iteration():
    seed = L(0x808000, 'sta $7e0000', A=0x0000, DB=0, ea=0x7E0000, val=0x0000, P=P8, width=2)
    lines = [seed,
             L(0x80800F, 'mvn $7e,$7e', A=2, X=0, Y=1), L(0x80800F, 'mvn $7e,$7e', A=1, X=1, Y=2),
             L(0x80800F, 'mvn $7e,$7e', A=0, X=2, Y=3), L(0x808012, 'nop')]
    r = run(lines, watch={'T': 0x0002})
    assert r['meta']['block_bytes_modeled'] == 3
    ev = [e for e in r['events'] if e['access'] == 'block_move']
    assert ev and ev[0]['value_after'] == 0 and ev[0]['confidence'] == 'DERIVADO'


def test_mvn_collapsed_in_one_line():
    lines = [L(0x808000, 'sta $7e0000', A=0, ea=0x7E0000, val=0, P=P8, width=2),
             L(0x80800F, 'mvn $7e,$7e', A=0xFFFE, X=0, Y=1), L(0x808012, 'nop')]
    r = run(lines, watch={'T': 0x3BAE})
    assert r['meta']['block_bytes_modeled'] == 0xFFFF
    e = [e for e in r['events'] if e['access'] == 'block_move'][0]
    assert e['value_after'] == 0 and 'colapsado' in e['evidence']


def test_mvn_unknown_source_is_not_invented():
    r = run([L(0x80800F, 'mvn $7e,$7e', A=0, X=0x3BAD, Y=0x3BAE), L(0x808012, 'nop')], watch={'T': 0x3BAE})
    e = r['events'][0]
    assert e['value_after'] is None and e['confidence'] == 'NÃO VERIFICADO'


def test_mvp_copies_downwards():
    lines = [L(0x808000, 'sta $7e0003', A=0x0055, ea=0x7E0003, val=0, P=P8, width=2),
             L(0x80800F, 'mvp $7e,$7e', A=0, X=3, Y=4, P=P8), L(0x808012, 'nop')]
    r = run(lines, watch={'W': 0x0004})
    e = [e for e in r['events'] if e['access'] == 'block_move'][0]
    assert e['value_after'] == 0x55


def test_mvn_truncated_trace_flagged():
    r = run([L(0x80800F, 'mvn $7e,$7e', A=5, X=0, Y=1)], watch={'T': 0x0001})
    assert 'truncado' in r['events'][0]['evidence']


# ---- CPU x SPC700 ------------------------------------------------------------------------------------------------
def test_spc700_lines_are_separated():
    r = run(['0200 mov a,#$00', '[SPC] 0201 bne $0200', 'SPC: 0203 nop', L(0x808000, 'nop'),
             L(0x808001, 'sta $1c59', ea=0x7E1C59, val=0, A=1)])
    m = r['meta']
    assert m['spc700_lines'] == 3 and m['cpu_lines'] == 2 and m['malformed_lines'] == 0
    assert len(r['events']) == 1


def test_spc_lines_do_not_break_cpu_continuity():
    r = run([L(0x808000, 'nop'), '0200 mov a,#$00', L(0x808001, 'nop')])
    assert r['meta']['discontinuities'] == 0


# ---- truncamento, fluxo, robustez -------------------------------------------------------------------------------
def test_discontinuity_detected():
    r = run([L(0x808000, 'nop'), L(0x808005, 'nop')])
    assert r['meta']['discontinuities'] == 1 and r['anomalies']['discontinuities'][0]['esperado'] == '$80:8001'


def test_branch_target_is_not_discontinuity():
    r = run([L(0x808000, 'bne $808010'), L(0x808010, 'nop'), L(0x808011, 'jmp $9000'), L(0x809000, 'nop')])
    assert r['meta']['discontinuities'] == 0


def test_return_redirect_vs_normal_return():
    normal = run([L(0x808000, 'jsl $86a1f6'), L(0x86A1F6, 'rtl'), L(0x808004, 'nop')])
    assert normal['meta']['return_redirects'] == 0
    redir = run([L(0x808000, 'jsl $88c7b6'), L(0x88C7B6, 'rtl'), L(0x84A3F4, 'nop')])
    assert redir['meta']['return_redirects'] == 1
    assert redir['anomalies']['return_redirects'][0]['esperado'] == '$80:8004'


def test_return_without_call_marks_truncated_start():
    r = run([L(0x86A206, 'rtl'), L(0x808004, 'nop')])
    assert any('sem chamada' in n for n in r['meta']['truncation_notes'])


def test_incomplete_tail_and_round_number_notes():
    raw = (L(0x808000, 'nop') + '\n' + '808001 sta $1c').encode()
    assert any('cortada' in n for n in analyze_bytes(raw)['meta']['truncation_notes'])
    full = ('\n'.join(L(0x808000 + i % 2 * 0, 'nop') for i in range(10000)) + '\n')
    assert any('número redondo' in n for n in analyze_lines(full.splitlines())['meta']['truncation_notes'])


@pytest.mark.parametrize('raw', [b'', b'\n\n', b'\xff\xfe\x00garbage', b'86A203 lda $1c59 [$7E1C59] = $ZZZZ\n',
                                 b'86A203 lda ' + b'A' * 5000 + b'\n', b'999999999 nop\n', b'# comentario\n',
                                 b'86A203 sta ($94),y [$7E3A50]\n', bytes(range(256)) * 40])
def test_malformed_input_does_not_raise(raw):
    r = analyze_bytes(raw)
    assert 'meta' in r and r['meta']['events'] >= 0


def test_empty_trace_reports_no_instructions():
    assert any('Nenhuma instrução' in n for n in analyze_bytes(b'')['meta']['truncation_notes'])


def test_size_limit():
    with pytest.raises(ValueError):
        analyze_bytes(b'x' * (128 * 1024 * 1024 + 1))


# ---- roster, grafo e exportação -----------------------------------------------------------------------------------
EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'hidden_roster_trace_sintetico.txt'


def test_roster_transitions_from_synthetic_trace():
    r = analyze_bytes(EXAMPLE.read_bytes())
    assert [n for _, n in r['roster']['sequence']] == ['Idels', 'Shao Kahn', 'Motaro', 'Sheeva', 'Human Smoke', 'Idels']
    known = [w for w in r['roster']['writes'] if w['writer_known_statically']]
    assert len(known) == 5 and all(w['consistent_with_static'] is True for w in known)
    assert r['meta']['memory_mismatches'] == 0 and r['meta']['return_redirects'] == 1
    assert 'NESTE trace' in r['roster']['note']


def test_static_writer_mismatch_is_reported():
    # escrita em $C4:A349 com valor diferente do estático (0x1B) deve ser marcada como inconsistente
    r = run([L(0xC4A346, 'lda #$0005'), L(0xC4A349, 'sta $1c59', ea=0x7E1C59, val=0x19, A=0x0005)])
    w = r['roster']['writes'][0]
    assert w['static_expected_value'] == 0x1B and w['consistent_with_static'] is False


def test_synthetic_example_is_reproducible(tmp_path):
    from tools.make_synthetic_trace import main, OUT, PC
    OUT.clear(); PC[0] = 0
    out = tmp_path / 't.txt'
    main([str(out)])
    assert out.read_text() == EXAMPLE.read_text()


def test_graph_distinguishes_executed_from_static():
    raw = bytearray(0x10000)
    raw[0x8000:0x8002] = bytes([0xD0, 0x04])        # bne $C0:8006
    rom = Rom(bytes(raw)); rom.mapping = 'exhirom'
    r = run([L(0xC08000, 'bne $c08006'), L(0xC08006, 'nop')], rom=rom)
    ev = {(e['from'], e['to']): e['evidence'] for e in r['graph']['edges']}
    assert ev[('$C0:8000', '$C0:8006')] == 'EXECUTADO + ESTÁTICO'
    assert ev[('$C0:8000', '$C0:8002')].startswith('INFERIDO')


def test_csv_and_filters():
    r = analyze_bytes(EXAMPLE.read_bytes())
    csv_text = events_to_csv(r['events'])
    assert csv_text.splitlines()[0].startswith('n,seq,pc,pc_canon,instruction,access')
    assert len(csv_text.splitlines()) == len(r['events']) + 1
    assert all('1C59' in e['vars'] for e in filter_events(r['events'], var='$7E:1C59'))
    assert {e['character'] for e in filter_events(r['events'], character='motaro')} == {'Motaro'}
    assert all(e['confidence'] == 'CONFIRMADO' for e in filter_events(r['events'], min_confidence='CONFIRMADO'))


@pytest.mark.skipif(not os.environ.get('UMK3_TRACE'), reason='defina UMK3_TRACE=caminho de um trace real do Mesen')
def test_real_trace_smoke():
    r = analyze_bytes(Path(os.environ['UMK3_TRACE']).read_bytes())
    assert r['meta']['cpu_lines'] > 0
