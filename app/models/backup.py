"""备份与容灾业务模型：备份任务、恢复演练、保留策略。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class BackupJob(Base):
    """备份任务：定义一次备份的调度、对象与保留。"""

    __tablename__ = "backup_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    schedule: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    target_system: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    backup_type: Mapped[str] = mapped_column(String(16), default="full")
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(16), default="enabled", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RestoreDrill(Base):
    """恢复演练：基于备份任务执行一次恢复验证。"""

    __tablename__ = "restore_drills"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    backup_job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    planned_date: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RetentionPolicy(Base):
    """保留策略：按策略维度控制备份副本的保留与归档。"""

    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    strategy: Mapped[str] = mapped_column(String(16), default="weekly")
    keep_count: Mapped[int] = mapped_column(Integer, default=30)
    archive_after_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
