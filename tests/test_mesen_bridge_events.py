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
    encode({**event(), 'address': '7E3A50'}),
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
