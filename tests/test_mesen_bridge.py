"""Contrato do agente de captura Mesen e geração de perfis."""
import pytest

from backend.mesen_bridge import generate_capture_script, _list_addrs


def test_default_agent_generated():
    lua = generate_capture_script()
    assert 'emu.addMemoryCallback' in lua
    assert 'emu.callbackType.exec' in lua
    assert 'emu.callbackType.write' in lua
    assert 'local SESSION_ID = "exp001_run01"' in lua
    assert '0x86A353' in lua and '0x03A50' in lua
    assert 'value_after_status":"unknown"' in lua


def test_extra_start_pc_and_wram_mapping():
    lua = generate_capture_script(
        pc='86A34F',
        cpu_points='86A355',
        wram_points='7E0C0E,7F0002',
        session_id='exp002_run01',
        max_events=500,
    )
    assert '0x86A34F, 0x86A355' in lua
    assert '0x00C0E, 0x10002' in lua
    assert 'local MAX_EVENTS = 500' in lua


@pytest.mark.parametrize("pc,wram,session", [
    ('86GG55', '0C0E', 'exp001'),
    ('86A353', '20000', 'exp001'),
    ('86A353', '0C0E', 'exp 001'),
])
def test_validation_rejects_invalid_input(pc, wram, session):
    with pytest.raises(ValueError):
        generate_capture_script(pc=pc, cpu_points='86A355',
                                wram_points=wram, session_id=session)


def test_cpu_dedupe_and_multiple_wram():
    assert _list_addrs('86:A353, $86A353', kind='CPU') == [0x86A353]
    assert _list_addrs('7E0C0E,7F0C0E', kind='WRAM') == [0x0C0E, 0x10C0E]


def test_tab_present():
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / 'backend' / 'static' / 'index.html'
    html = p.read_text(encoding='utf-8')
    assert 'data-tab="execution"' in html
    assert 'function renderExecutionResearch()' in html
    assert '/api/mesen-bridge/script?' in html
