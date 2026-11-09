"""Read-only bridge: existing Studio projects -> Intelligence jobs.

Reuses Store's persisted ROM artifacts; no second upload and no edits to the
existing Studio API or frontend. Only projects with a saved ROM are eligible.
"""
from __future__ import annotations

import hashlib
import re
import threading

from .intelligence_core import IntelligenceService, validate_rom
from .storage import Store

PROJECT_ID = re.compile(r"^[0-9a-f]{12}$")


class ProjectBridge:
    def __init__(self, store: Store, service: IntelligenceService, *, max_per_scan: int = 4):
        self.store = store
        self.service = service
        self.max_per_scan = max_per_scan
        self.lock = threading.RLock()
        self.associations = {}  # project id -> {rom_sha, job_id}
        self.offset = 0
        self.last_errors = {}

    def _check_id(self, pid):
        if not PROJECT_ID.fullmatch(pid):
            raise KeyError(pid)

    def scan_project(self, pid):
        """Schedule analysis for a persisted ROM. No ROM payload in return."""
        self._check_id(pid)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        sha = project.get("rom_sha")
        if not sha:
            with self.lock:
                self.associations.pop(pid, None)
                self.last_errors.pop(pid, None)
            return {"project_id": pid, "status": "no_rom", "rom_sha": None, "job_id": None}
        with self.lock:
            cached = self.associations.get(pid)
        if cached and cached["rom_sha"] == sha:
            job = self.service.status(cached["job_id"])
            if job is not None:
                return {"project_id": pid, "rom_sha": sha, "job_id": job["id"],
                        "status": job["status"], "stage": job["stage"]}
        try:
            raw = self.store.load_artifact(sha)
            if raw is None:
                raise ValueError("Artefato ROM ausente no armazenamento do projeto")
            validate_rom(raw)
            if hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("SHA-256 não corresponde ao artefato ROM armazenado")
            job = self.service.submit(raw)
            with self.lock:
                self.associations[pid] = {"rom_sha": sha, "job_id": job["id"]}
                self.last_errors.pop(pid, None)
            return {"project_id": pid, "rom_sha": sha, "job_id": job["id"],
                    "status": job["status"], "stage": job["stage"]}
        except (ValueError, OSError) as exc:
            with self.lock:
                self.associations.pop(pid, None)
                self.last_errors[pid] = str(exc)
            return {"project_id": pid, "rom_sha": sha, "job_id": None,
                    "status": "artifact_error", "error": str(exc)}

    def scan_once(self):
        """Bounded, fair pass over persisted projects; safe to run repeatedly."""
        projects = self.store.projects()
        if not projects:
            return []
        count = min(self.max_per_scan, len(projects))
        with self.lock:
            start = self.offset % len(projects)
            self.offset = (start + count) % len(projects)
        return [self.scan_project(projects[(start + i) % len(projects)]["id"])
                for i in range(count)]

    def status(self, pid):
        self._check_id(pid)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        sha = project.get("rom_sha")
        if not sha:
            return {"project_id": pid, "rom_sha": None, "status": "no_rom", "job_id": None}
        with self.lock:
            assoc = self.associations.get(pid)
            error = self.last_errors.get(pid)
        if assoc and assoc["rom_sha"] == sha:
            job = self.service.status(assoc["job_id"])
            if job:
                return {"project_id": pid, "rom_sha": sha, "status": job["status"],
                        "job_id": job["id"], "stage": job["stage"],
                        "stages": job["stages"], "error": job["error"]}
        if error:
            return {"project_id": pid, "rom_sha": sha, "status": "artifact_error",
                    "job_id": None, "error": error}
        return {"project_id": pid, "rom_sha": sha, "status": "pending_detection", "job_id": None}

    def list_statuses(self):
        return [self.status(p["id"]) for p in self.store.projects()]
