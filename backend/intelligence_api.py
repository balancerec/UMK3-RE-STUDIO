"""Isolated local read-only Intelligence API (phase 1).

Run: python -m uvicorn backend.intelligence_api:app --host 127.0.0.1 --port 3091
Does not hook the existing Studio server or publish ROM contents.
"""
from __future__ import annotations

import re
from fastapi import FastAPI, File, HTTPException, UploadFile
from .intelligence_core import IntelligenceService, MAX_ROM_BYTES

app = FastAPI(title="UMK3 Intelligence API", version="0.1.0")
service = IntelligenceService()
VALID_ID = re.compile(r"^[0-9a-f]{32}$")


def get_job(job_id: str):
    if not VALID_ID.fullmatch(job_id):
        raise HTTPException(404, "Job desconhecido")
    job = service.status(job_id)
    if job is None:
        raise HTTPException(404, "Job desconhecido")
    return job


@app.post("/api/intelligence/import", status_code=202)
async def import_rom(file: UploadFile = File(...)):
    """Start a bounded background analysis. ROM data are never exposed in responses."""
    try:
        raw = await file.read(MAX_ROM_BYTES + 1)
        if len(raw) > MAX_ROM_BYTES:
            raise HTTPException(413, "ROM excede o limite de importação")
        try:
            return service.submit(raw)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/intelligence/jobs/{job_id}")
def job_status(job_id: str):
    return get_job(job_id)


def completed_result(job_id: str):
    job = get_job(job_id)
    if job["status"] == "failed":
        raise HTTPException(409, {"status": "failed", "error": job["error"]})
    if job["status"] != "completed":
        raise HTTPException(202, {"status": job["status"], "stage": job["stage"]})
    payload = service.result(job_id)
    if not payload or payload["result"] is None:
        raise HTTPException(503, "Cache de análise indisponível")
    return payload["result"]


@app.get("/api/intelligence/jobs/{job_id}/summary")
def summary(job_id: str):
    return completed_result(job_id)["summary"]


@app.get("/api/intelligence/jobs/{job_id}/identity")
def identity(job_id: str):
    return completed_result(job_id)["identity"]


@app.get("/api/intelligence/jobs/{job_id}/banks")
def banks(job_id: str, start: int = 0, limit: int = 64):
    if start < 0 or not 1 <= limit <= 128:
        raise HTTPException(422, "Paginação inválida")
    return completed_result(job_id)["banks"][start:start + limit]


@app.get("/api/intelligence/jobs/{job_id}/entrypoints")
def entrypoints(job_id: str):
    return completed_result(job_id)["entrypoints"]


@app.get("/api/intelligence/jobs/{job_id}/xrefs")
def xrefs(job_id: str, start: int = 0, limit: int = 100):
    if start < 0 or not 1 <= limit <= 500:
        raise HTTPException(422, "Paginação inválida")
    x = completed_result(job_id)["control_flow"]
    return {"total": len(x["references"]), "truncated": x["truncated"],
            "items": x["references"][start:start + limit]}


@app.get("/api/intelligence/jobs/{job_id}/evidence")
def evidence(job_id: str, start: int = 0, limit: int = 100, category: str | None = None):
    if start < 0 or not 1 <= limit <= 500:
        raise HTTPException(422, "Paginação inválida")
    rows = completed_result(job_id)["evidence"]
    if category is not None:
        if category not in ("entrypoint", "xref"):
            raise HTTPException(422, "Categoria inválida")
        rows = [r for r in rows if r["category"] == category]
    return {"total": len(rows), "items": rows[start:start + limit]}


@app.get("/api/intelligence/health")
def health():
    return {"status": "ok", "mode": "local_only", "rom_bytes_exposed": False}
