"""备份与容灾业务仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backup import BackupJob, RestoreDrill, RetentionPolicy


# ── 备份任务 ──
async def get_job(session: AsyncSession, job_id: str) -> BackupJob | None:
    result = await session.execute(select(BackupJob).where(BackupJob.id == job_id))
    return result.scalar_one_or_none()


async def get_job_by_name(session: AsyncSession, name: str) -> BackupJob | None:
    result = await session.execute(select(BackupJob).where(BackupJob.name == name))
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, keyword: str | None = None,
) -> list[BackupJob]:
    stmt = select(BackupJob).order_by(BackupJob.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(BackupJob.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(BackupJob.name.like(like), BackupJob.target_system.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_jobs(session: AsyncSession, status: str | None = None,
                     keyword: str | None = None) -> int:
    stmt = select(func.count(BackupJob.id))
    if status:
        stmt = stmt.where(BackupJob.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(BackupJob.name.like(like), BackupJob.target_system.like(like)))
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_job(session: AsyncSession, job: BackupJob) -> BackupJob:
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# ── 恢复演练 ──
async def get_drill(session: AsyncSession, drill_id: str) -> RestoreDrill | None:
    result = await session.execute(select(RestoreDrill).where(RestoreDrill.id == drill_id))
    return result.scalar_one_or_none()


async def list_drills(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, backup_job_id: str | None = None,
) -> list[RestoreDrill]:
    stmt = select(RestoreDrill).order_by(RestoreDrill.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(RestoreDrill.status == status)
    if backup_job_id:
        stmt = stmt.where(RestoreDrill.backup_job_id == backup_job_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_drills(session: AsyncSession, status: str | None = None,
                       backup_job_id: str | None = None) -> int:
    stmt = select(func.count(RestoreDrill.id))
    if status:
        stmt = stmt.where(RestoreDrill.status == status)
    if backup_job_id:
        stmt = stmt.where(RestoreDrill.backup_job_id == backup_job_id)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_drill(session: AsyncSession, drill: RestoreDrill) -> RestoreDrill:
    session.add(drill)
    await session.commit()
    await session.refresh(drill)
    return drill


# ── 保留策略 ──
async def get_policy(session: AsyncSession, policy_id: str) -> RetentionPolicy | None:
    result = await session.execute(select(RetentionPolicy).where(RetentionPolicy.id == policy_id))
    return result.scalar_one_or_none()


async def get_policy_by_name(session: AsyncSession, name: str) -> RetentionPolicy | None:
    result = await session.execute(select(RetentionPolicy).where(RetentionPolicy.name == name))
    return result.scalar_one_or_none()


async def list_policies(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None,
) -> list[RetentionPolicy]:
    stmt = select(RetentionPolicy).order_by(RetentionPolicy.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(RetentionPolicy.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_policies(session: AsyncSession, status: str | None = None) -> int:
    stmt = select(func.count(RetentionPolicy.id))
    if status:
        stmt = stmt.where(RetentionPolicy.status == status)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def save_policy(session: AsyncSession, policy: RetentionPolicy) -> RetentionPolicy:
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy
