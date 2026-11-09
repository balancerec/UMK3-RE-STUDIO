"""UMK3 Intelligence Core v1: bounded, reproducible ROM-only analysis.

Runs independently of backend.server and the Hidden Roster trace pipeline.
No commercial ROM bytes are written to the intelligence cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .analysis import build_xrefs, seed_roots
from .core import Rom, cpu_to_file, file_to_cpu

MAX_ROM_BYTES = 16 * 1024 * 1024 + 512
ANALYZER_VERSION = "1.0.0"
KNOWN_ROM_SHA = "f512ef861f0df2dbb8f9563fb5f3b01ab70b7048ac329a9262ff3d34ca487bdd"
STAGES = ("identity", "banks", "entrypoints", "control_flow")
EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="umk3-intel")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_rom(data: bytes):
    if not 32768 <= len(data) <= MAX_ROM_BYTES:
        raise ValueError("ROM deve ter entre 32 KiB e 16 MiB + 512 bytes")
    if len(data) % 32768 not in (0, 512):
        raise ValueError("Tamanho SNES incompatível")


def analyze_rom(data: bytes, progress=None) -> dict:
    """Analyze a ROM in memory. Static results are not proof of execution."""
    validate_rom(data)
    callback = progress or (lambda _name, _status: None)
    rom = Rom(data)
    callback("identity", "running")
    metadata = rom.metadata()
    identity = {
        **metadata,
        "raw_sha256": hashlib.sha256(data).hexdigest(),
        "known_deluxe_2_2": metadata["sha256"] == KNOWN_ROM_SHA,
        "confidence": "confirmed_from_bytes",
    }
    callback("identity", "completed")

    callback("banks", "running")
    banks = rom.banks()
    callback("banks", "completed")

    callback("entrypoints", "running")
    roots = seed_roots(rom)
    callback("entrypoints", "completed")

    callback("control_flow", "running")
    root_offsets = list(dict.fromkeys(r["offset"] for r in roots if r["name"] == "reset"))
    xrefs = build_xrefs(rom, root_offsets, max_instructions=3000, max_entries=10000) if root_offsets else {
        "roots": [], "instructions": 0, "references": [], "ambiguous": [],
        "truncated": False, "limitations": "Nenhum vetor de reset mapeável encontrado.",
    }
    callback("control_flow", "completed")

    evidence = []
    for root in roots:
        evidence.append({
            "id": f"entrypoint-{root['name']}",
            "category": "entrypoint",
            "source": "rom_header_static",
            "confidence": "static_candidate",
            "cpu": f"{root['cpu']:06X}",
            "rom_offset": root["offset"],
            "note": "Vetor presente no cabeçalho; não confirma execução.",
        })
    for i, ref in enumerate(xrefs["references"][:10000]):
        evidence.append({
            "id": f"xref-{i}", "category": "xref",
            "source": "static_disassembly",
            "confidence": "static_candidate",
            "rom_offset": ref["from_offset"],
            "cpu": f"{ref['from_cpu']:06X}" if ref.get("from_cpu") is not None else None,
            "target_rom_offset": ref.get("to_offset"),
            "target_cpu": f"{ref['to_cpu']:06X}" if ref.get("to_cpu") is not None else None,
            "kind": ref["kind"],
            "note": "Transferência de controle inferida estaticamente; não é trace.",
        })
    return {
        "schema_version": 1,
        "analyzer_version": ANALYZER_VERSION,
        "completed_at": utc_now(),
        "identity": identity,
        "banks": banks,
        "entrypoints": roots,
        "control_flow": xrefs,
        "evidence": evidence,
        "summary": {
            "rom_sha256": metadata["sha256"],
            "mapping": metadata["mapping"],
            "banks": len(banks),
            "entrypoints": len(roots),
            "instructions_scanned": xrefs["instructions"],
            "xrefs": len(xrefs["references"]),
            "truncated": xrefs["truncated"],
            "observed_execution": False,
            "pending_inputs": ["mesen_trace", "wram_dump", "vram_dump", "mlb_symbols"],
        },
    }


class IntelligenceService:
    """Job coordinator with JSON result cache keyed by ROM SHA and analyzer version."""

    def __init__(self, root=None, executor=None):
        self.root = Path(root or Path(os.environ.get("UMK3_STUDIO_HOME", str(Path.home() / ".umk3-re-studio"))) / "intelligence")
        self.root.mkdir(parents=True, exist_ok=True)
        self.executor = executor or EXECUTOR
        self.lock = threading.RLock()
        self.jobs = {}

    def _cache_path(self, sha):
        return self.root / f"{ANALYZER_VERSION}-{sha}.json"

    def submit(self, data: bytes):
        validate_rom(data)
        sha = hashlib.sha256(data).hexdigest()
        with self.lock:
            for job in self.jobs.values():
                if job["raw_sha256"] == sha and job["status"] in ("queued", "running", "completed"):
                    return dict(job)
            job_id = uuid.uuid4().hex
            job = {
                "id": job_id, "raw_sha256": sha, "status": "queued",
                "stage": None, "stages": {s: "pending" for s in STAGES},
                "created_at": utc_now(), "updated_at": utc_now(),
                "error": None,
            }
            path = self._cache_path(sha)
            if path.is_file():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                    if cached["analyzer_version"] == ANALYZER_VERSION and cached["identity"]["raw_sha256"] == sha:
                        job.update(status="completed", stage="cache", stages={s: "completed" for s in STAGES})
                        self.jobs[job_id] = job
                        return dict(job)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            self.jobs[job_id] = job
            try:
                self.executor.submit(self._run, job_id, data)
            except RuntimeError as exc:
                job.update(status="failed", error=str(exc))
            return dict(job)

    def _run(self, job_id, data):
        with self.lock:
            self.jobs[job_id].update(status="running", updated_at=utc_now())

        def progress(stage, status):
            with self.lock:
                job = self.jobs[job_id]
                job["stage"] = stage
                job["stages"][stage] = status
                job["updated_at"] = utc_now()

        try:
            result = analyze_rom(data, progress)
            sha = self.jobs[job_id]["raw_sha256"]
            target = self._cache_path(sha)
            temp = target.with_name(f".{uuid.uuid4().hex}.tmp")
            try:
                temp.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
            with self.lock:
                self.jobs[job_id].update(status="completed", updated_at=utc_now())
        except Exception as exc:
            with self.lock:
                self.jobs[job_id].update(status="failed", error=f"{type(exc).__name__}: {exc}", updated_at=utc_now())

    def status(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def result(self, job_id):
        job = self.status(job_id)
        if job is None:
            return None
        if job["status"] != "completed":
            return {"job": job, "result": None}
        path = self._cache_path(job["raw_sha256"])
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"job": job, "result": None, "error": "Resultado em cache indisponível"}
        return {"job": job, "result": result}
