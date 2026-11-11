"""Testes de backend.dragon_slot: ROM sintética (sempre) e ROM real (opcional, UMK3_ROM)."""
import os
import pytest
from backend.core import Rom
from backend import dragon_slot as D

UP = bytes([0,1,2,3,4,5,6,0,1,2,3,4,5,6,8,9,10,11,12,14,15,16,17,18])
DOWN = bytes([7,8,9,10,11,12,13,7,14,15,16,17,18,13,19,20,21,22,23,19,20,21,22,23])
LEFT = bytes([0,0,1,2,3,4,5,7,7,8,9,10,11,12,14,14,15,16,17,19,19,20,21,22])
RIGHT = bytes([1,2,3,4,5,6,6,8,9,10,11,12,13,13,15,16,17,18,18,20,21,22,23,13])


OPERANDS = {0x07: 0x86, 0x15: 0x0A, 0x18: 0x5D, 0x1D: 1, 0x20: 0x17, 0x25: 2, 0x27: 0, 0x29: 0x0A, 0x2F: 0, 0x34: 0,
            0x36: 0x9C, 0x37: 0xA7, 0x3B: 0xC6, 0x3C: 0xA6, 0x3E: 9, 0x42: 3, 0x47: 0x2E, 0x4B: 0xDE, 0x4C: 0xA6,
            0x4E: 9, 0x52: 0x10, 0x57: 0x1E, 0x5B: 0xF6, 0x5C: 0xA6, 0x5E: 9, 0x62: 9, 0x67: 0x0E, 0x6B: 0x0E,
            0x6C: 0xA7, 0x6E: 7, 0x72: 0x0B}


def routine(**over):
    ops = dict(OPERANDS)
    ops.update(over)
    return bytes(b if b is not None else ops[i] for i, b in enumerate(D.SKELETON))


def make_rom(at=0x06A726, **over):
    d = bytearray(0x800000)
    h = 0x40FFC0
    d[h:h + 21] = b'SYNTHETIC UMK3 TEST  '[:21]
    d[h + 0x15] = 0x35
    d[h + 0x1C:h + 0x20] = bytes([0x00, 0x00, 0xFF, 0xFF])
    r = routine(**over)
    d[at:at + len(r)] = r
    for ptr, tab in zip((0xA6C6, 0xA6DE, 0xA6F6, 0xA70E), (UP, DOWN, LEFT, RIGHT)):
        d[0x060000 + ptr:0x060000 + ptr + 24] = tab
    return Rom(bytes(d), 'synthetic')


def test_skeleton_length():
    assert len(D.SKELETON) == 0x76


def test_synthetic_mapping_is_exhirom():
    assert make_rom().mapping == 'exhirom'


def test_synthetic_decode_and_tables():
    rom = make_rom()
    d = D.decode_dispatch(rom)
    assert d['found'] and d['rom_offset'] == 0x06A726 and d['special_index'] == 0x0A and d['state_gate_value'] == 1
    assert d['table_bank'] == 0x86 and d['dead_branches_converge'] and d['special_miss_goes_to_end']
    assert d['redirects']['up']['table_ptr'] == 0xA6C6 and d['redirects']['up']['axis'] == 'vertical'
    t = D.read_tables(rom, d)
    assert t['nav']['up'] == UP and t['nav']['right'] == RIGHT


def test_synthetic_relocated_routine_found_by_signature():
    rom = make_rom(at=0x0A1230)
    d = D.decode_dispatch(rom)
    # nada fica em $86:A726 neste ROM: o endereço conhecido falha e a assinatura acha uma única ocorrência
    assert d['found'] and d['rom_offset'] == 0x0A1230 and 'assinatura' in d['how_located']


def test_synthetic_patched_gate_detected():
    # variante estilo "Extended Edition": CMP #$0A -> #$FF (especial desativado)
    d = D.decode_dispatch(Rom(bytes(_patch(make_rom(), 0x06A726 + 0x15, 0xFF)), 'p'))
    assert d['special_index'] == 0xFF


def _patch(rom, off, val):
    b = bytearray(rom.data)
    b[off] = val
    return b


def test_navigate_logic_without_rom():
    disp = {'special_index': 10, 'state_gate_value': 1,
            'redirects': {'up': {'target_index': 3, 'axis': 'vertical'}, 'down': {'target_index': 16, 'axis': 'vertical'},
                          'left': {'target_index': 9, 'axis': 'horizontal'}, 'right': {'target_index': 11, 'axis': 'horizontal'}}}
    nav = {'up': UP, 'down': DOWN, 'left': LEFT, 'right': RIGHT}
    r = D.navigate(nav, disp, 16, 'up', 0)
    assert (r['next'], r['redirected'], r['step_scale']) == (3, True, 2)      # Ermac -> Jax pulando o Dragão
    assert D.navigate(nav, disp, 3, 'down', 0)['next'] == 16                  # Jax -> Ermac
    assert D.navigate(nav, disp, 16, 'up', 1)['next'] == 10                   # estado 1 libera o slot
    r0 = D.reachability(nav, disp, 0)
    r1 = D.reachability(nav, disp, 1)
    assert r0['unreachable'] == [10] and r1['unreachable'] == []
    assert {e['from'] for e in r0['special_entries']} == {3, 9, 11, 16}


REAL = os.environ.get('UMK3_ROM')
real = pytest.mark.skipif(not REAL or not os.path.exists(REAL), reason='defina UMK3_ROM com a ROM Deluxe 2.2')


@pytest.fixture(scope='module')
def rom():
    return Rom(open(REAL, 'rb').read(), 'real')


@real
def test_real_sha(rom):
    import hashlib
    assert hashlib.sha256(rom.data).hexdigest() == D.ROM_SHA256


@real
def test_real_dispatch_and_redirects(rom):
    d = D.decode_dispatch(rom)
    assert d['found'] and d['rom_offset'] == 0x06A726
    assert d['special_index'] == 0x0A and d['state_gate_value'] == 1 and d['dead_branches_converge']
    assert {k: v['target_index'] for k, v in d['redirects'].items()} == {'up': 3, 'down': 0x10, 'left': 9, 'right': 0x0B}


@real
def test_real_ermac_jax_and_reachability(rom):
    a = D.analyze(rom)
    nav, d = a['_nav'], a['dispatch']
    assert nav['up'][0x10] == 0x0A and nav['down'][3] == 0x0A          # CONFIRMADO POR CÓDIGO: tabelas
    assert D.navigate(nav, d, 0x10, 'up', 0)['next'] == 3
    assert D.navigate(nav, d, 3, 'down', 0)['next'] == 0x10
    assert a['reachability']['state_0']['unreachable'] == [0x0A]
    assert a['reachability']['state_1']['unreachable'] == []
    # regressão: nenhum outro lutador fica inacessível
    assert set(a['reachability']['state_0']['reachable']) == set(range(24)) - {0x0A}


@real
def test_real_all_facts_verified(rom):
    a = D.analyze(rom)
    assert a['state_1c57']['all_access_points_verified'] and a['portrait']['verified'] and a['cycle']['verified']
