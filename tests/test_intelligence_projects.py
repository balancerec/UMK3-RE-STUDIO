"""Tests for Intelligence project bridge and automatic persisted-ROM detection."""
import hashlib
import time
from concurrent.futures import Future

from fastapi.testclient import TestClient

from backend import intelligence_api
from backend.intelligence_core import IntelligenceService
from backend.intelligence_projects import ProjectBridge
from backend.storage import Store


class InlineExecutor:
    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


def sample_rom(marker=0):
    data = bytearray([0xFF]) * 0x10000
    data[0xFFC0:0xFFD5] = b"INTELLIGENCE PROJECTS".ljust(21, b" ")
    data[0xFFD5] = 0x21
    data[0xFFDC:0xFFE0] = b"\xFF\xFF\x00\x00"
    data[0xFFFC:0xFFFE] = b"\x00\x80"
    data[0x8000] = 0x6B  # RTL
    data[0x0200] = marker
    return bytes(data)


def setup(tmp_path):
    store = Store(tmp_path / "studio")
    service = IntelligenceService(tmp_path / "intel", executor=InlineExecutor())
    return store, service, ProjectBridge(store, service)


def test_bridge_requires_saved_rom_and_resuses_existing_artifacts(tmp_path):
    store, service, bridge = setup(tmp_path)
    p = store.create("Deluxe")
    assert bridge.scan_project(p["id"])["status"] == "no_rom"
    raw = sample_rom()
    sha = store.save_artifact(p["id"], "rom_sha", raw, "game.sfc")
    scheduled = bridge.scan_project(p["id"])
    assert scheduled["status"] == "completed"
    assert scheduled["rom_sha"] == sha
    assert service.result(scheduled["job_id"])["result"]["identity"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert bridge.scan_project(p["id"])["job_id"] == scheduled["job_id"]
    assert bridge.status(p["id"])["status"] == "completed"

    new = sample_rom(marker=3)
    new_sha = store.save_artifact(p["id"], "rom_sha", new, "changed.sfc")
    after = bridge.scan_project(p["id"])
    assert after["rom_sha"] == new_sha
    assert after["job_id"] != scheduled["job_id"]
    assert bridge.status(p["id"])["status"] == "completed"


def test_bridge_refuses_corrupt_artifact(tmp_path):
    store, service, bridge = setup(tmp_path)
    p = store.create("Corrupt")
    raw = sample_rom()
    sha = store.save_artifact(p["id"], "rom_sha", raw, "rom.sfc")
    (store.artifacts / sha).write_bytes(sample_rom(marker=13))
    status = bridge.scan_project(p["id"])
    assert status["status"] == "artifact_error"
    assert "SHA-256" in status["error"]
    assert service.jobs == {}


def test_scan_once_is_bounded_and_round_robin(tmp_path):
    store, _, bridge = setup(tmp_path)
    bridge.max_per_scan = 2
    ids = []
    for i in range(5):
        p = store.create(f"Project{i}")
        store.save_artifact(p["id"], "rom_sha", sample_rom(i), f"rom{i}.sfc")
        ids.append(p["id"])
    got = []
    for _ in range(3):
        got.extend(x["project_id"] for x in bridge.scan_once())
    assert set(got) == set(ids)
    assert len(got) == 6
    assert all(bridge.status(pid)["status"] == "completed" for pid in ids)


def test_project_endpoints_and_automatic_detection(tmp_path, monkeypatch):
    store, service, bridge = setup(tmp_path)
    monkeypatch.setattr(intelligence_api, "service", service)
    monkeypatch.setattr(intelligence_api, "bridge", bridge)
    project = store.create("UI linked")
    pid = project["id"]
    with TestClient(intelligence_api.app) as client:
        assert client.get(f"/api/intelligence/projects/{pid}").json()["status"] == "no_rom"
        # Simulate an existing Studio import after the Intelligence API starts.
        store.save_artifact(pid, "rom_sha", sample_rom(), "Deluxe.sfc")
        deadline = time.monotonic() + 3
        current = None
        while time.monotonic() < deadline:
            current = client.get(f"/api/intelligence/projects/{pid}").json()
            if current["status"] == "completed":
                break
            time.sleep(0.03)
        assert current["status"] == "completed", current
        assert current["job_id"]
        assert client.get("/api/intelligence/projects").json()["projects"][0]["project_id"] == pid
        assert client.get(f"/api/intelligence/projects/{pid}/summary").json()["banks"] == 1
        assert client.get(f"/api/intelligence/projects/{pid}/evidence", params={"category": "entrypoint"}).status_code == 200
        assert client.get(f"/api/intelligence/projects/{pid}/evidence", params={"limit": 999}).status_code == 422
        assert client.post(f"/api/intelligence/projects/{pid}/analyze").json()["job_id"] == current["job_id"]
        assert client.get("/api/intelligence/projects/not-a-project").status_code == 404
        assert client.get(f"/api/intelligence/projects/{pid}/summary").status_code == 200


def test_project_status_never_returns_original_rom_bytes(tmp_path):
    store, _, bridge = setup(tmp_path)
    p = store.create("Protected")
    raw = sample_rom(marker=47)
    store.save_artifact(p["id"], "rom_sha", raw, "rom.sfc")
    result = bridge.scan_project(p["id"])
    assert "data" not in result and "bytes" not in result
    assert not any(f.suffix == ".sfc" for f in bridge.service.root.iterdir())
