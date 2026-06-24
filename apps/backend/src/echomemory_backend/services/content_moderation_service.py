"""内容审核任务、结果应用和统计维护服务。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.comment import Comment
from echomemory_backend.models.content_moderation import (
    ContentModerationHistory,
    ContentModerationTask,
    UserContentModerationStats,
)
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.schemas.content_moderation import ModerationDecision
from echomemory_backend.services.notification_service import create_notification

logger = logging.getLogger(__name__)

ContentType = Literal["comment", "space_post"]
_CONTENT_MODELS = {"comment": Comment, "space_post": SpacePost}
_STATS_ADVISORY_LOCK_NAMESPACE = 73102


def _utcnow() -> datetime:
    """返回带时区的 UTC 当前时间。"""
    return datetime.now(timezone.utc)


def classify_safety_score(score: int) -> str:
    """按确认阈值把 0–10 安全分映射为档位。"""
    if not 0 <= score <= 10:
        raise ValueError("safety score must be between 0 and 10")
    if score <= 3:
        return "DANGEROUS"
    if score <= 6:
        return "RISKY"
    return "SAFE"


def classify_recommendation_score(score: int) -> str:
    """按确认阈值把 0–10 推荐分映射为档位。"""
    if not 0 <= score <= 10:
        raise ValueError("recommendation score must be between 0 and 10")
    return "RECOMMENDED" if score >= 8 else "NORMAL"


async def _get_content(
    db: AsyncSession,
    content_type: ContentType,
    content_id: int,
    *,
    for_update: bool = False,
) -> Comment | SpacePost | None:
    """按统一内容类型加载记录。"""
    model = _CONTENT_MODELS[content_type]
    stmt = select(model).where(model.id == content_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def enqueue_moderation(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
    force: bool = False,
    commit: bool = False,
) -> ContentModerationTask:
    """为内容幂等创建审核任务；强制重审时递增版本。"""
    content = await _get_content(
        db, content_type, content_id, for_update=force
    )
    if content is None:
        raise ValueError("content not found")

    if force:
        content.moderation_version += 1
        content.moderation_status = "PENDING"
        content.moderation_reason = None

    existing = (
        await db.execute(
            select(ContentModerationTask).where(
                ContentModerationTask.content_type == content_type,
                ContentModerationTask.content_id == content_id,
                ContentModerationTask.moderation_version
                == content.moderation_version,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    task = ContentModerationTask(
        content_type=content_type,
        content_id=content_id,
        moderation_version=content.moderation_version,
    )
    db.add(task)
    await db.flush()
    if commit:
        await db.commit()
        await db.refresh(task)
    return task


async def claim_pending_tasks(
    db: AsyncSession,
    *,
    limit: int = 10,
    lease_seconds: int = 300,
) -> list[ContentModerationTask]:
    """使用 SKIP LOCKED 领取可处理或租约过期的审核任务。"""
    now = _utcnow()
    stale_before = now - timedelta(seconds=lease_seconds)
    stmt = (
        select(ContentModerationTask)
        .where(
            ContentModerationTask.attempt_count
            < ContentModerationTask.max_attempts,
            or_(
                (
                    (ContentModerationTask.status == "PENDING")
                    & (ContentModerationTask.available_at <= now)
                ),
                (
                    (ContentModerationTask.status == "PROCESSING")
                    & (ContentModerationTask.locked_at < stale_before)
                ),
            ),
        )
        .order_by(
            ContentModerationTask.available_at,
            ContentModerationTask.id,
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    tasks = list((await db.execute(stmt)).scalars().all())
    for task in tasks:
        task.status = "PROCESSING"
        task.locked_at = now
    await db.commit()
    return tasks


async def _get_or_create_stats(
    db: AsyncSession, user_id: int
) -> UserContentModerationStats:
    """锁定并返回用户审核统计行。"""
    await db.execute(
        select(
            func.pg_advisory_xact_lock(
                _STATS_ADVISORY_LOCK_NAMESPACE,
                user_id,
            )
        )
    )
    stats = (
        await db.execute(
            select(UserContentModerationStats)
            .where(UserContentModerationStats.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if stats is None:
        stats = UserContentModerationStats(user_id=user_id)
        db.add(stats)
        await db.flush()
    return stats


def _adjust_stats(
    stats: UserContentModerationStats,
    *,
    safety_level: str | None,
    recommendation_level: str | None,
    delta: int,
) -> None:
    """对用户统计应用一条有效结果的差量。"""
    if safety_level == "RISKY":
        stats.risky_count = max(0, stats.risky_count + delta)
    elif safety_level == "DANGEROUS":
        stats.dangerous_count = max(0, stats.dangerous_count + delta)
    if recommendation_level == "RECOMMENDED":
        stats.recommended_count = max(0, stats.recommended_count + delta)


async def apply_moderation_decision(
    db: AsyncSession,
    *,
    task: ContentModerationTask,
    decision: ModerationDecision,
    source: Literal["AGENT", "MANUAL"] = "AGENT",
    reviewer_user_id: int | None = None,
    agent_run_id: UUID | None = None,
) -> bool:
    """原子应用有效审核结果；过期版本返回 False。"""
    locked_task = (
        await db.execute(
            select(ContentModerationTask)
            .where(ContentModerationTask.id == task.id)
            .with_for_update()
        )
    ).scalar_one()
    if locked_task.status in {"SUCCEEDED", "CANCELLED"}:
        return False
    content = await _get_content(
        db,
        locked_task.content_type,
        locked_task.content_id,
        for_update=True,
    )
    if content is None or content.moderation_version != locked_task.moderation_version:
        locked_task.status = "CANCELLED"
        await db.commit()
        return False

    safety_level = classify_safety_score(decision.safety_score)
    recommendation_level = classify_recommendation_score(
        decision.recommendation_score
    )
    stats = await _get_or_create_stats(db, content.user_id)
    if (
        content.safety_level is not None
        and content.recommendation_level is not None
    ):
        _adjust_stats(
            stats,
            safety_level=content.safety_level,
            recommendation_level=content.recommendation_level,
            delta=-1,
        )
    _adjust_stats(
        stats,
        safety_level=safety_level,
        recommendation_level=recommendation_level,
        delta=1,
    )

    content.safety = decision.safety_score
    content.recommendation_score = decision.recommendation_score
    content.safety_level = safety_level
    content.recommendation_level = recommendation_level
    content.moderation_status = "MANUAL" if source == "MANUAL" else "SUCCEEDED"
    content.moderation_reason = decision.reason
    content.moderated_at = _utcnow()
    content.is_recommended = recommendation_level == "RECOMMENDED"

    if (
        safety_level == "DANGEROUS"
        and content.deletion_reason != "USER"
    ):
        content.is_deleted = True
        content.deletion_reason = "MODERATION_DANGEROUS"
        await create_notification(
            db,
            recipient_id=content.user_id,
            actor_id=None,
            type=NotificationType.CONTENT_MODERATION,
            target_type=locked_task.content_type,
            target_id=content.id,
            extra={
                "action": "deleted",
                "reason": decision.reason,
                "safety_level": safety_level,
            },
        )

    history = ContentModerationHistory(
        content_type=locked_task.content_type,
        content_id=content.id,
        user_id=content.user_id,
        moderation_version=locked_task.moderation_version,
        source=source,
        safety_score=decision.safety_score,
        recommendation_score=decision.recommendation_score,
        safety_level=safety_level,
        recommendation_level=recommendation_level,
        reason=decision.reason,
        agent_run_id=agent_run_id,
        reviewer_user_id=reviewer_user_id,
    )
    db.add(history)
    locked_task.status = "SUCCEEDED"
    locked_task.locked_at = None
    locked_task.last_error = None
    locked_task.agent_run_id = agent_run_id
    await db.commit()
    return True


async def mark_moderation_attempt_failed(
    db: AsyncSession,
    *,
    task_id: int,
    error: BaseException,
    agent_run_id: UUID | None = None,
) -> bool:
    """记录失败并决定重试；第三次失败时隐藏内容。"""
    task = (
        await db.execute(
            select(ContentModerationTask)
            .where(ContentModerationTask.id == task_id)
            .with_for_update()
        )
    ).scalar_one()
    if task.status in {"SUCCEEDED", "CANCELLED", "FAILED"}:
        return task.status == "FAILED"
    task.attempt_count += 1
    task.last_error = f"{type(error).__name__}: {error}"[:2000]
    task.agent_run_id = agent_run_id
    task.locked_at = None
    terminal = task.attempt_count >= task.max_attempts
    if not terminal:
        task.status = "PENDING"
        task.available_at = _utcnow() + timedelta(
            seconds=2 ** (task.attempt_count - 1)
        )
        content = await _get_content(
            db, task.content_type, task.content_id, for_update=True
        )
        if (
            content is not None
            and content.moderation_version == task.moderation_version
        ):
            content.moderation_status = "PENDING"
            content.moderation_reason = task.last_error
        await db.commit()
        return False

    task.status = "FAILED"
    content = await _get_content(
        db, task.content_type, task.content_id, for_update=True
    )
    if content is not None and content.moderation_version == task.moderation_version:
        content.moderation_status = "FAILED"
        content.moderation_reason = task.last_error
        content.moderated_at = _utcnow()
        if content.deletion_reason != "USER":
            content.is_deleted = True
            content.deletion_reason = "MODERATION_FAILED"
            await create_notification(
                db,
                recipient_id=content.user_id,
                actor_id=None,
                type=NotificationType.CONTENT_MODERATION,
                target_type=task.content_type,
                target_id=content.id,
                extra={
                    "action": "hidden_after_failures",
                    "reason": "自动审核连续失败，内容已暂时隐藏",
                },
            )
    await db.commit()
    return True


async def cancel_moderation_task(
    db: AsyncSession,
    *,
    task_id: int,
    reason: str,
) -> None:
    """取消已失去对应内容或已过期的任务。"""
    task = (
        await db.execute(
            select(ContentModerationTask)
            .where(ContentModerationTask.id == task_id)
            .with_for_update()
        )
    ).scalar_one()
    if task.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        return
    task.status = "CANCELLED"
    task.locked_at = None
    task.last_error = reason[:2000]
    await db.commit()


async def restore_moderation_deleted_content(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
) -> Comment | SpacePost:
    """恢复仅因自动审核而逻辑删除的内容。"""
    content = await _get_content(db, content_type, content_id, for_update=True)
    if content is None:
        raise ValueError("content not found")
    if content.deletion_reason not in {
        "MODERATION_DANGEROUS",
        "MODERATION_FAILED",
    }:
        raise ValueError("content was not deleted by moderation")
    content.is_deleted = False
    content.deletion_reason = None
    await db.commit()
    return content
