"""备份与容灾业务 Pydantic 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ── 备份任务 ──
class BackupJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    schedule: str = Field(min_length=1, max_length=128)
    target_system: str = Field(min_length=1, max_length=128)
    backup_type: Literal["full", "incremental", "differential"] = "full"
    retention_days: int = Field(default=30, ge=1, le=3650)


class BackupJobUpdate(BaseModel):
    schedule: str | None = Field(default=None, max_length=128)
    target_system: str | None = Field(default=None, max_length=128)
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class BackupJobStatusUpdate(BaseModel):
    status: Literal["enabled", "paused", "failed", "completed"]


# ── 恢复演练 ──
class RestoreDrillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    backup_job_id: str = Field(min_length=1, max_length=64)
    planned_date: str = Field(default="", max_length=32)


class RestoreDrillFinish(BaseModel):
    result_summary: str = Field(default="", max_length=2000)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    passed: bool = True


class RestoreDrillStatusUpdate(BaseModel):
    status: Literal["planned", "in_progress", "passed", "failed"]


# ── 保留策略 ──
class RetentionPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    strategy: Literal["daily", "weekly", "monthly", "yearly"] = "weekly"
    keep_count: int = Field(default=30, ge=1, le=10000)
    archive_after_days: int = Field(default=0, ge=0, le=3650)


class RetentionPolicyUpdate(BaseModel):
    strategy: Literal["daily", "weekly", "monthly", "yearly"] | None = None
    keep_count: int | None = Field(default=None, ge=1, le=10000)
    archive_after_days: int | None = Field(default=None, ge=0, le=3650)


class RetentionPolicyStatusUpdate(BaseModel):
    status: Literal["active", "disabled"]
