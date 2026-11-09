"""Intelligence Core regression tests with synthetic, redistributable ROMs."""
import hashlib
import json
from concurrent.futures import Future

import pytest
from fastapi.testclient import TestClient

from backend.core import Rom
from backend.intelligence_core import IntelligenceService, analyze_rom, validate_rom
from backend import intelligence_api


class InlineExecutor:
    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


def synthetic_rom():
    data = bytearray([0xFF]) * 65536
    header = 0xFFC0
    data[header:header + 21] = b"TEST INTELLIGENCE".ljust(21, b" ")
    data[header + 0x15] = 0x21
    data[header + 0x1C:header + 0x20] = bytes([0xFF, 0xFF, 0, 0])
    data[header + 0x3C:header + 0x3E] = (0x8000).to_bytes(2, "little")
    data[0x8000] = 0x6B  # RTL; bounded scan halts
    return bytes(data)


def test_static_analysis_respects_evidence_classes():
    raw = synthetic_rom()
    result = analyze_rom(raw)
    assert result["identity"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["summary"]["observed_execution"] is False
    assert result["identity"]["known_deluxe_2_2"] is False
    assert len(result["banks"]) == 1
    assert result["summary"]["instructions_scanned"] <= 3000
    assert all(e["source"] in ("rom_header_static", "static_disassembly") for e in result["evidence"])
    assert result["summary"]["pending_inputs"]


def test_job_caching_and_no_rom_storage(tmp_path):
    root = tmp_path / "intel"
    service = IntelligenceService(root, executor=InlineExecutor())
    raw = synthetic_rom()
    first = service.submit(raw)
    assert first["status"] == "completed"
    assert all(x == "completed" for x in first["stages"].values())
    assert service.result(first["id"])["result"]["summary"]["banks"] == 1
    assert service.submit(raw)["id"] == first["id"]
    second_process = IntelligenceService(root, executor=InlineExecutor())
    cached = second_process.submit(raw)
    assert cached["status"] == "completed"
    assert cached["stage"] == "cache"
    files = list(root.iterdir())
    assert len(files) == 1 and files[0].suffix == ".json"
    content = json.loads(files[0].read_text(encoding="utf-8"))
    assert content["identity"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "rom_bytes" not in content
    assert "rom_data" not in content


def test_size_and_invalid_rom_rejected(tmp_path):
    for raw in (b"", b"x" * 32769, b"x" * (16 * 1024 * 1024 + 513)):
        with pytest.raises(ValueError):
            validate_rom(raw)
    service = IntelligenceService(tmp_path, executor=InlineExecutor())
    with pytest.raises(ValueError):
        service.submit(b"invalid")
    assert service.jobs == {}


def test_api_import_status_summary_and_evidence(tmp_path, monkeypatch):
    service = IntelligenceService(tmp_path, executor=InlineExecutor())
    monkeypatch.setattr(intelligence_api, "service", service)
    with TestClient(intelligence_api.app) as client:
        r = client.post("/api/intelligence/import", files={"file": ("demo.sfc", synthetic_rom())})
        assert r.status_code == 202, r.text
        job_id = r.json()["id"]
        assert client.get(f"/api/intelligence/jobs/{job_id}").json()["status"] == "completed"
        assert client.get(f"/api/intelligence/jobs/{job_id}/summary").json()["banks"] == 1
        assert client.get(f"/api/intelligence/jobs/{job_id}/identity").json()["known_deluxe_2_2"] is False
        assert len(client.get(f"/api/intelligence/jobs/{job_id}/banks").json()) == 1
        entries = client.get(f"/api/intelligence/jobs/{job_id}/entrypoints").json()
        assert any(e["name"] == "reset" for e in entries)
        assert client.get(f"/api/intelligence/jobs/{job_id}/evidence", params={"category": "entrypoint"}).status_code == 200
        assert client.get(f"/api/intelligence/jobs/{job_id}/xrefs").status_code == 200
        assert client.get(f"/api/intelligence/jobs/{job_id}/evidence", params={"limit": 999}).status_code == 422
        assert client.get("/api/intelligence/jobs/not-a-real-id").status_code == 404
        assert client.post("/api/intelligence/import", files={"file": ("bad.sfc", b"x")}).status_code == 422
        assert client.get("/api/intelligence/health").json()["rom_bytes_exposed"] is False
