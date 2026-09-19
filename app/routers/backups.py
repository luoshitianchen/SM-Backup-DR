"""备份与容灾业务路由：备份任务 / 恢复演练 / 保留策略。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
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
from app.services.backup import BackupService

router = APIRouter(prefix="/api/backup", tags=["backup-dr"])


# ── 备份任务 ──
@router.get("/jobs")
async def list_jobs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.list_jobs(session, limit=limit, offset=offset,
                                         status_filter=status_filter, keyword=keyword)


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: BackupJobCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.create_job(session, payload, request)


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.get_job(session, job_id)


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: str, payload: BackupJobUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.update_job(session, job_id, payload, request)


@router.patch("/jobs/{job_id}/status")
async def update_job_status(
    job_id: str, payload: BackupJobStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.update_job_status(session, job_id, payload, request)


# ── 恢复演练 ──
@router.get("/drills")
async def list_drills(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    backup_job_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.list_drills(session, limit=limit, offset=offset,
                                            status_filter=status_filter,
                                            backup_job_id=backup_job_id)


@router.post("/drills", status_code=status.HTTP_201_CREATED)
async def create_drill(
    payload: RestoreDrillCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.create_drill(session, payload, request)


@router.get("/drills/{drill_id}")
async def get_drill(
    drill_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.get_drill(session, drill_id)


@router.patch("/drills/{drill_id}/status")
async def update_drill_status(
    drill_id: str, payload: RestoreDrillStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.update_drill_status(session, drill_id, payload, request)


@router.post("/drills/{drill_id}/finish")
async def finish_drill(
    drill_id: str, payload: RestoreDrillFinish, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.finish_drill(session, drill_id, payload, request)


# ── 保留策略 ──
@router.get("/policies")
async def list_policies(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.list_policies(session, limit=limit, offset=offset,
                                             status_filter=status_filter)


@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    payload: RetentionPolicyCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.create_policy(session, payload, request)


@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.get_policy(session, policy_id)


@router.patch("/policies/{policy_id}")
async def update_policy(
    policy_id: str, payload: RetentionPolicyUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.update_policy(session, policy_id, payload, request)


@router.patch("/policies/{policy_id}/status")
async def update_policy_status(
    policy_id: str, payload: RetentionPolicyStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await BackupService.update_policy_status(session, policy_id, payload, request)
