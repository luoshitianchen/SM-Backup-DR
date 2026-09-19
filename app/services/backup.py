"""备份与容灾业务服务层：任务/演练/保留策略全生命周期。"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.backup import BackupJob, RestoreDrill, RetentionPolicy
from app.repositories import backup as repo
from app.schemas.backup import (
    BackupJobCreate,
    BackupJobStatusUpdate,
    BackupJobUpdate,
    RestoreDrillCreate,
    RestoreDrillFinish,
    RestoreDrillStatusUpdate,
    RetentionPolicyCreate,
    RetentionPolicyStatusUpdate,
    RetentionPolicyUpdate,
)
from app.services.audit import record_audit

# 备份任务状态机：允许的迁移
_JOB_TRANSITIONS = {
    "enabled": {"paused", "failed", "completed"},
    "paused": {"enabled"},
    "failed": {"enabled"},
    "completed": set(),
}

# 恢复演练状态机：允许的迁移
_DRILL_TRANSITIONS = {
    "planned": {"in_progress"},
    "in_progress": {"passed", "failed"},
    "passed": set(),
    "failed": set(),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _job_to_dict(j: BackupJob) -> dict:
    return {
        "id": j.id, "name": j.name, "schedule": j.schedule,
        "target_system": j.target_system, "backup_type": j.backup_type,
        "retention_days": j.retention_days, "status": j.status,
        "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
        "created_at": j.created_at.isoformat() if j.created_at else "",
        "updated_at": j.updated_at.isoformat() if j.updated_at else "",
    }


def _drill_to_dict(d: RestoreDrill) -> dict:
    return {
        "id": d.id, "name": d.name, "backup_job_id": d.backup_job_id,
        "planned_date": d.planned_date, "status": d.status,
        "result_summary": d.result_summary, "duration_minutes": d.duration_minutes,
        "created_at": d.created_at.isoformat() if d.created_at else "",
        "updated_at": d.updated_at.isoformat() if d.updated_at else "",
    }


def _policy_to_dict(p: RetentionPolicy) -> dict:
    return {
        "id": p.id, "name": p.name, "strategy": p.strategy,
        "keep_count": p.keep_count, "archive_after_days": p.archive_after_days,
        "status": p.status,
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


class BackupService:
    """备份与容灾领域服务。"""

    # ── 鉴权统一入口 ──
    @staticmethod
    def _require_write(request: Request) -> None:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")

    # ── 备份任务 ──
    @staticmethod
    async def list_jobs(session: AsyncSession, limit: int = 100, offset: int = 0,
                        status_filter: str | None = None, keyword: str | None = None) -> dict:
        jobs = await repo.list_jobs(session, limit=limit, offset=offset,
                                    status=status_filter, keyword=keyword)
        total = await repo.count_jobs(session, status=status_filter, keyword=keyword)
        return {"total": total, "items": [_job_to_dict(j) for j in jobs]}

    @staticmethod
    async def get_job(session: AsyncSession, job_id: str) -> dict:
        job = await repo.get_job(session, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "备份任务不存在")
        return _job_to_dict(job)

    @staticmethod
    async def create_job(session: AsyncSession, payload: BackupJobCreate, request: Request) -> dict:
        BackupService._require_write(request)
        if await repo.get_job_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "备份任务名称已存在")
        job = BackupJob(
            id=str(uuid.uuid4()), name=payload.name, schedule=payload.schedule,
            target_system=payload.target_system, backup_type=payload.backup_type,
            retention_days=payload.retention_days, status="enabled",
        )
        job = await repo.save_job(session, job)
        await record_audit(session, "backup.job.created", "internal",
                           f"job_id={job.id} name={payload.name}", request)
        return _job_to_dict(job)

    @staticmethod
    async def update_job(session: AsyncSession, job_id: str,
                         payload: BackupJobUpdate, request: Request) -> dict:
        BackupService._require_write(request)
        job = await repo.get_job(session, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "备份任务不存在")
        if payload.schedule is not None:
            job.schedule = payload.schedule
        if payload.target_system is not None:
            job.target_system = payload.target_system
        if payload.retention_days is not None:
            job.retention_days = payload.retention_days
        job = await repo.save_job(session, job)
        await record_audit(session, "backup.job.updated", "internal",
                           f"job_id={job_id}", request)
        return _job_to_dict(job)

    @staticmethod
    async def update_job_status(session: AsyncSession, job_id: str,
                                payload: BackupJobStatusUpdate, request: Request) -> dict:
        BackupService._require_write(request)
        job = await repo.get_job(session, job_id)
        if not job:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "备份任务不存在")
        new_status = payload.status
        if new_status == job.status:
            return _job_to_dict(job)
        if new_status not in _JOB_TRANSITIONS.get(job.status, set()):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"非法状态迁移: {job.status} -> {new_status}")
        job.status = new_status
        if new_status in ("completed", "failed"):
            job.last_run_at = datetime.now(UTC)
        job = await repo.save_job(session, job)
        await record_audit(session, "backup.job.status_changed", "internal",
                           f"job_id={job_id} status={new_status}", request)
        return _job_to_dict(job)

    # ── 恢复演练 ──
    @staticmethod
    async def list_drills(session: AsyncSession, limit: int = 100, offset: int = 0,
                          status_filter: str | None = None,
                          backup_job_id: str | None = None) -> dict:
        drills = await repo.list_drills(session, limit=limit, offset=offset,
                                        status=status_filter, backup_job_id=backup_job_id)
        total = await repo.count_drills(session, status=status_filter, backup_job_id=backup_job_id)
        return {"total": total, "items": [_drill_to_dict(d) for d in drills]}

    @staticmethod
    async def get_drill(session: AsyncSession, drill_id: str) -> dict:
        drill = await repo.get_drill(session, drill_id)
        if not drill:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "恢复演练不存在")
        return _drill_to_dict(drill)

    @staticmethod
    async def create_drill(session: AsyncSession, payload: RestoreDrillCreate,
                           request: Request) -> dict:
        BackupService._require_write(request)
        if not await repo.get_job(session, payload.backup_job_id):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "关联的备份任务不存在")
        drill = RestoreDrill(
            id=str(uuid.uuid4()), name=payload.name, backup_job_id=payload.backup_job_id,
            planned_date=payload.planned_date, status="planned",
        )
        drill = await repo.save_drill(session, drill)
        await record_audit(session, "backup.drill.created", "internal",
                           f"drill_id={drill.id} name={payload.name}", request)
        return _drill_to_dict(drill)

    @staticmethod
    async def update_drill_status(session: AsyncSession, drill_id: str,
                                  payload: RestoreDrillStatusUpdate, request: Request) -> dict:
        BackupService._require_write(request)
        drill = await repo.get_drill(session, drill_id)
        if not drill:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "恢复演练不存在")
        new_status = payload.status
        if new_status == drill.status:
            return _drill_to_dict(drill)
        if new_status not in _DRILL_TRANSITIONS.get(drill.status, set()):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"非法状态迁移: {drill.status} -> {new_status}")
        drill.status = new_status
        drill = await repo.save_drill(session, drill)
        await record_audit(session, "backup.drill.status_changed", "internal",
                           f"drill_id={drill_id} status={new_status}", request)
        return _drill_to_dict(drill)

    @staticmethod
    async def finish_drill(session: AsyncSession, drill_id: str,
                           payload: RestoreDrillFinish, request: Request) -> dict:
        BackupService._require_write(request)
        drill = await repo.get_drill(session, drill_id)
        if not drill:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "恢复演练不存在")
        if drill.status != "in_progress":
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                               "仅进行中的演练可完成")
        drill.status = "passed" if payload.passed else "failed"
        drill.result_summary = payload.result_summary
        drill.duration_minutes = payload.duration_minutes
        drill = await repo.save_drill(session, drill)
        await record_audit(session, "backup.drill.finished", "internal",
                           f"drill_id={drill_id} result={drill.status}", request)
        return _drill_to_dict(drill)

    # ── 保留策略 ──
    @staticmethod
    async def list_policies(session: AsyncSession, limit: int = 100, offset: int = 0,
                            status_filter: str | None = None) -> dict:
        policies = await repo.list_policies(session, limit=limit, offset=offset,
                                            status=status_filter)
        total = await repo.count_policies(session, status=status_filter)
        return {"total": total, "items": [_policy_to_dict(p) for p in policies]}

    @staticmethod
    async def get_policy(session: AsyncSession, policy_id: str) -> dict:
        policy = await repo.get_policy(session, policy_id)
        if not policy:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "保留策略不存在")
        return _policy_to_dict(policy)

    @staticmethod
    async def create_policy(session: AsyncSession, payload: RetentionPolicyCreate,
                            request: Request) -> dict:
        BackupService._require_write(request)
        if await repo.get_policy_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "保留策略名称已存在")
        policy = RetentionPolicy(
            id=str(uuid.uuid4()), name=payload.name, strategy=payload.strategy,
            keep_count=payload.keep_count, archive_after_days=payload.archive_after_days,
            status="active",
        )
        policy = await repo.save_policy(session, policy)
        await record_audit(session, "backup.policy.created", "internal",
                           f"policy_id={policy.id} name={payload.name}", request)
        return _policy_to_dict(policy)

    @staticmethod
    async def update_policy(session: AsyncSession, policy_id: str,
                            payload: RetentionPolicyUpdate, request: Request) -> dict:
        BackupService._require_write(request)
        policy = await repo.get_policy(session, policy_id)
        if not policy:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "保留策略不存在")
        if payload.strategy is not None:
            policy.strategy = payload.strategy
        if payload.keep_count is not None:
            policy.keep_count = payload.keep_count
        if payload.archive_after_days is not None:
            policy.archive_after_days = payload.archive_after_days
        policy = await repo.save_policy(session, policy)
        await record_audit(session, "backup.policy.updated", "internal",
                           f"policy_id={policy_id}", request)
        return _policy_to_dict(policy)

    @staticmethod
    async def update_policy_status(session: AsyncSession, policy_id: str,
                                   payload: RetentionPolicyStatusUpdate, request: Request) -> dict:
        BackupService._require_write(request)
        policy = await repo.get_policy(session, policy_id)
        if not policy:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "保留策略不存在")
        policy.status = payload.status
        policy = await repo.save_policy(session, policy)
        await record_audit(session, "backup.policy.status_changed", "internal",
                           f"policy_id={policy_id} status={payload.status}", request)
        return _policy_to_dict(policy)
