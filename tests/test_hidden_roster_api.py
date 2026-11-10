"""Endpoints /api/hidden-roster/*. Requer FastAPI (ignorado se ausente)."""
from pathlib import Path
import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
import backend.server as srv

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples' / 'hidden_roster_trace_sintetico.txt'


def test_analyze_export_flow(monkeypatch):
    monkeypatch.setitem(srv._HR_LAST, 'result', None)
    c = TestClient(srv.app)
    assert c.get('/api/hidden-roster/export.csv').status_code == 400
    r = c.post('/api/hidden-roster/analyze', files={'file': ('trace.txt', EXAMPLE.read_bytes())})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [n for _, n in body['roster']['sequence']] == ['Idels', 'Shao Kahn', 'Motaro', 'Sheeva', 'Human Smoke', 'Idels']
    assert c.get('/api/hidden-roster/status').json()['loaded'] is True
    csv_text = c.get('/api/hidden-roster/export.csv', params={'var': '1C59'}).text
    assert csv_text.splitlines()[0].startswith('n,seq,pc')
    j = c.get('/api/hidden-roster/export.json', params={'character': 'Motaro'}).json()
    assert {e['character'] for e in j['events']} == {'Motaro'}


def test_malformed_upload_is_not_a_server_error(monkeypatch):
    monkeypatch.setitem(srv._HR_LAST, 'result', None)
    c = TestClient(srv.app)
    r = c.post('/api/hidden-roster/analyze', files={'file': ('x.bin', bytes(range(256)) * 10)})
    assert r.status_code == 200 and r.json()['meta']['events'] == 0
    assert c.post('/api/hidden-roster/analyze', params={'max_events': 0},
                  files={'file': ('x.txt', b'')}).status_code == 422
