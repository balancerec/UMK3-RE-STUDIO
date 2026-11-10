"""Validação de importação JSONL de eventos do agente Mesen."""
import json

import pytest
from backend.mesen_bridge_events import analyze_capture_jsonl


def event(seq=1, kind='memory_write', mem='WRAM', addr='003A50'):
    return {
        'schema_version': '0.1',
        'session_id': 'exp001_run01',
        'seq': seq, 'kind': kind, 'cpu': 'snes',
        'memory_space': mem, 'address': addr,
        'callback_value': 10,
        'value_before': None, 'value_after': None,
        'value_after_status': 'unknown', 'registers': {'A': 10},
    }


def encode(*events):
    return ('\n'.join(json.dumps(x) for x in events) + '\n').encode()


def test_jsonl_event_counts_and_uncertainty():
    data = analyze_capture_jsonl(encode(event(), event(2, 'cpu_execute', 'CPU', '86A353')))
    assert data['events'] == 2
    assert data['unknown_after_values'] == 2
    assert data['events_by_type'] == {'memory_write': 1, 'cpu_execute': 1}
    assert data['cpu_hotspots'][0]['pc'] == '86A353'


@pytest.mark.parametrize('payload', [
    b'{}\n',
    b'not-json\n',
    encode(event(), event()),
    encode(event(), {**event(2), 'session_id': 'exp002_run01'}),
])
def test_bad_capture_rejected(payload):
    with pytest.raises(ValueError):
        analyze_capture_jsonl(payload)


def test_empty_rejected_and_ui_upload():
    with pytest.raises(ValueError):
        analyze_capture_jsonl(b'')
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / 'backend/static/index.html').read_text(encoding='utf-8')
    assert 'id="erjsonl"' in html
    assert '/api/mesen-bridge/analyze' in html


def test_mesen_mixed_wram_address_formats_from_real_exp001():
    """A same WRAM location may arrive as absolute bus or physical offset."""
    from backend.mesen_bridge_events import normalize_wram_address
    payload = encode(
        event(1, addr='000C0E'),
        event(2, addr='7E3A50'),
        event(3, addr='003A50'),
        event(4, addr='7F0C0E'),
    )
    result = analyze_capture_jsonl(payload)
    observed = {row['address']: row['hits'] for row in result['observed_addresses']}
    assert observed['WRAM:03A50'] == 2
    assert observed['WRAM:00C0E'] == 1
    assert observed['WRAM:10C0E'] == 1
    assert result['recent_events'][1]['raw_address'] == '7E3A50'
    assert result['recent_events'][1]['address'] == '03A50'
    assert normalize_wram_address(0x7F0000) == 0x10000


@pytest.mark.parametrize('address', ['800000', '20000', '7DFFFF', 'FFFFFF'])
def test_out_of_range_wram_rejected(address):
    with pytest.raises(ValueError):
        analyze_capture_jsonl(encode(event(addr=address)))
