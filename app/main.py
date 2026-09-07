"""SM Backup DR —— 备份与灾备中心：备份任务、快照、恢复演练与保留策略。"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-backup-dr"
VERSION = "3.0.0"
NAME = "SM Backup DR"
DESCRIPTION = "备份与灾备中心：备份任务、快照、恢复演练与保留策略"
PORT = 8430


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
                target TEXT NOT NULL, schedule TEXT NOT NULL DEFAULT 'daily',
                retention_days INTEGER NOT NULL DEFAULT 30, enabled INTEGER NOT NULL DEFAULT 1,
                last_run_at TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY, job_id TEXT NOT NULL, name TEXT NOT NULL,
                size_bytes INTEGER NOT NULL, checksum TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running', created_at TEXT NOT NULL,
                expires_at TEXT, restored_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_job ON snapshots(job_id, created_at DESC);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-object-storage", "sm-audit-log-center"],
    events=["backup.started", "backup.completed", "backup.restored"],
    overview_fn=lambda _r: {
        "summary": {
            "jobs": base.get_db().execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
            "snapshots": base.get_db().execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],
            "restored": base.get_db().execute("SELECT COUNT(*) FROM snapshots WHERE restored_at IS NOT NULL").fetchone()[0],
        }
    },
)
_init()


class JobIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    source: str = Field(min_length=2, max_length=300)
    target: str = Field(min_length=2, max_length=300)
    schedule: str = Field(default="daily", pattern=r"^(hourly|daily|weekly|monthly)$")
    retention_days: int = Field(default=30, ge=1, le=3650)


@app.get("/api/backup/jobs")
def list_jobs() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/backup/jobs", status_code=status.HTTP_201_CREATED)
def create_job(payload: JobIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    job_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO jobs (id, name, source, target, schedule, retention_days, enabled, last_run_at, created_at) VALUES (?,?,?,?,?,?,1,NULL,?)", (job_id, payload.name, payload.source, payload.target, payload.schedule, payload.retention_days, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "任务名已存在") from exc
        base.record_audit("backup.job_created", "internal", f"job={job_id} name={payload.name}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": job_id, "name": payload.name}


@app.post("/api/backup/jobs/{job_id}/run")
def run_job(job_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "备份任务不存在")
        if not job["enabled"]:
            raise HTTPException(status.HTTP_423_LOCKED, "备份任务已停用")
        snapshot_id = str(uuid.uuid4())
        size = secrets.randbelow(1024 * 1024 * 100) + 1024  # 模拟快照大小
        checksum = base.sm3_hex(f"{job['source']}|{size}|{_now()}".encode())
        expires = (datetime.now(UTC) + timedelta(days=job["retention_days"])).isoformat()
        conn.execute("INSERT INTO snapshots (id, job_id, name, size_bytes, checksum, status, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)", (snapshot_id, job_id, f"snap-{_now()[:10]}", size, checksum, "completed", _now(), expires))
        conn.execute("UPDATE jobs SET last_run_at=? WHERE id=?", (_now(), job_id))
        base.record_audit("backup.completed", "internal", f"job={job_id} snapshot={snapshot_id} bytes={size}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": snapshot_id, "job_id": job_id, "size_bytes": size, "checksum": checksum, "status": "completed"}


@app.get("/api/backup/snapshots")
def list_snapshots(job_id: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if job_id:
            rows = conn.execute("SELECT * FROM snapshots WHERE job_id=? ORDER BY created_at DESC", (job_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM snapshots ORDER BY created_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/backup/snapshots/{snapshot_id}/restore")
def restore_snapshot(snapshot_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        row = conn.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "快照不存在")
        if row["status"] != "completed":
            raise HTTPException(status.HTTP_409_CONFLICT, "快照不可恢复")
        conn.execute("UPDATE snapshots SET restored_at=? WHERE id=?", (_now(), snapshot_id))
        base.record_audit("backup.restored", "internal", f"snapshot={snapshot_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": snapshot_id, "restored_at": _now(), "message": "恢复演练完成"}


@app.get("/api/backup/policies")
def policies() -> dict[str, Any]:
    with base.db_ctx() as conn:
        jobs = [dict(r) for r in conn.execute("SELECT name, retention_days, schedule FROM jobs").fetchall()]
        expiring = conn.execute("SELECT COUNT(*) FROM snapshots WHERE expires_at IS NOT NULL AND expires_at < datetime('now', '+7 day')").fetchone()[0]
    return {"jobs": jobs, "expiring_within_7d": expiring}


@app.get("/api/backup/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes),0) FROM snapshots").fetchone()[0]
        return {
            "jobs": _count("SELECT COUNT(*) FROM jobs"),
            "snapshots": _count("SELECT COUNT(*) FROM snapshots"),
            "completed": _count("SELECT COUNT(*) FROM snapshots WHERE status='completed'"),
            "restored": _count("SELECT COUNT(*) FROM snapshots WHERE restored_at IS NOT NULL"),
            "total_bytes": int(total_bytes),
        }