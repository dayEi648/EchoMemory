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
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User
from echomemory_backend.schemas.content_moderation import ModerationDecision
from echomemory_backend.services.notification_service import create_notification

logger = logging.getLogger(__name__)

ContentType = Literal["comment", "space_post", "playlist", "user_profile"]
_CONTENT_MODELS = {
    "comment": Comment,
    "space_post": SpacePost,
    "playlist": Playlist,
    "user_profile": User,
}
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
) -> Comment | SpacePost | Playlist | User | None:
    """按统一内容类型加载记录。"""
    model = _CONTENT_MODELS[content_type]
    stmt = select(model).where(model.id == content_id)
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


def _get_safety_score(content: Comment | SpacePost | Playlist | User, content_type: ContentType) -> int | None:
    """读取内容的当前安全分（处理不同列名）。"""
    if content_type == "user_profile":
        return content.profile_safety_score  # type: ignore[union-attr]
    if content_type in ("comment", "space_post"):
        return content.safety  # type: ignore[union-attr]
    return content.safety_score  # type: ignore[union-attr]


def _set_moderation_fields(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
    *,
    safety_score: int,
    recommendation_score: int,
    safety_level: str,
    recommendation_level: str,
    moderation_status: str,
    moderation_reason: str | None,
) -> None:
    """在内容对象上设置审核结果字段（处理不同列名）。"""
    if content_type == "user_profile":
        content.profile_safety_score = safety_score  # type: ignore[union-attr]
        content.profile_recommendation_score = recommendation_score  # type: ignore[union-attr]
        content.profile_safety_level = safety_level  # type: ignore[union-attr]
        content.profile_recommendation_level = recommendation_level  # type: ignore[union-attr]
        content.profile_moderation_status = moderation_status  # type: ignore[union-attr]
        content.profile_moderation_reason = moderation_reason  # type: ignore[union-attr]
        content.profile_moderated_at = _utcnow()  # type: ignore[union-attr]
    elif content_type in ("comment", "space_post"):
        content.safety = safety_score  # type: ignore[union-attr]
        content.recommendation_score = recommendation_score  # type: ignore[union-attr]
        content.safety_level = safety_level  # type: ignore[union-attr]
        content.recommendation_level = recommendation_level  # type: ignore[union-attr]
        content.moderation_status = moderation_status  # type: ignore[union-attr]
        content.moderation_reason = moderation_reason  # type: ignore[union-attr]
        content.moderated_at = _utcnow()  # type: ignore[union-attr]
    else:
        content.safety_score = safety_score  # type: ignore[union-attr]
        content.recommendation_score = recommendation_score  # type: ignore[union-attr]
        content.safety_level = safety_level  # type: ignore[union-attr]
        content.recommendation_level = recommendation_level  # type: ignore[union-attr]
        content.moderation_status = moderation_status  # type: ignore[union-attr]
        content.moderation_reason = moderation_reason  # type: ignore[union-attr]
        content.moderated_at = _utcnow()  # type: ignore[union-attr]


def _get_moderation_version(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> int:
    """读取内容的审核版本号（处理不同列名）。"""
    if content_type == "user_profile":
        return content.profile_moderation_version  # type: ignore[union-attr]
    return content.moderation_version  # type: ignore[union-attr]


def _get_previous_safety_level(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> str | None:
    """读取内容的上一次安全档位。"""
    if content_type == "user_profile":
        return content.profile_safety_level  # type: ignore[union-attr]
    return content.safety_level  # type: ignore[union-attr]


def _get_previous_recommendation_level(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> str | None:
    """读取内容的上一次推荐档位。"""
    if content_type == "user_profile":
        return content.profile_recommendation_level  # type: ignore[union-attr]
    return content.recommendation_level  # type: ignore[union-attr]


def _get_content_owner_id(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> int:
    """读取内容的作者用户 ID。"""
    if content_type == "user_profile":
        return content.id  # type: ignore[union-attr]
    return content.user_id  # type: ignore[union-attr]


def _extract_content_preview(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
    max_length: int = 100,
) -> str:
    """提取被审核内容的文本预览（用于通知展示）。"""
    if content_type == "playlist":
        text = content.title  # type: ignore[union-attr]
    elif content_type == "user_profile":
        text = content.nickname  # type: ignore[union-attr]
    else:
        text = content.content or ""  # type: ignore[union-attr]
    if len(text) > max_length:
        text = text[:max_length] + "…"
    return text


def _is_user_deleted(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> bool:
    """检查该内容是否已被用户主动删除（不应被审核覆盖）。"""
    if content_type == "user_profile":
        return content.profile_deletion_reason == "USER"  # type: ignore[union-attr]
    return content.deletion_reason == "USER"  # type: ignore[union-attr]


def _apply_dangerous_action(
    content: Comment | SpacePost | Playlist | User,
    content_type: ContentType,
) -> bool:
    """对危险内容执行对应的安全动作。

    - comment / space_post: 逻辑删除
    - playlist: 清空标题和描述
    - user_profile: 清空昵称和简介

    返回是否需要发送通知。
    """
    if content_type == "playlist":
        content.title = "[审核未通过]"  # type: ignore[union-attr]
        content.description = ""  # type: ignore[union-attr]
        content.deletion_reason = "MODERATION_DANGEROUS"  # type: ignore[union-attr]
        return True
    if content_type == "user_profile":
        content.nickname = f"用户{content.id}"  # type: ignore[union-attr]
        content.bio = ""  # type: ignore[union-attr]
        content.profile_deletion_reason = "MODERATION_DANGEROUS"  # type: ignore[union-attr]
        return True
    content.is_deleted = True  # type: ignore[union-attr]
    content.deletion_reason = "MODERATION_DANGEROUS"  # type: ignore[union-attr]
    return True


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
    ct = locked_task.content_type
    if content is None or _get_moderation_version(content, ct) != locked_task.moderation_version:
        locked_task.status = "CANCELLED"
        await db.commit()
        return False

    safety_level = classify_safety_score(decision.safety_score)
    recommendation_level = classify_recommendation_score(decision.recommendation_score)

    owner_id = _get_content_owner_id(content, ct)
    stats = await _get_or_create_stats(db, owner_id)

    prev_safety = _get_previous_safety_level(content, ct)
    prev_recommendation = _get_previous_recommendation_level(content, ct)
    if prev_safety is not None and prev_recommendation is not None:
        _adjust_stats(
            stats,
            safety_level=prev_safety,
            recommendation_level=prev_recommendation,
            delta=-1,
        )
    _adjust_stats(
        stats,
        safety_level=safety_level,
        recommendation_level=recommendation_level,
        delta=1,
    )

    _set_moderation_fields(
        content,
        ct,
        safety_score=decision.safety_score,
        recommendation_score=decision.recommendation_score,
        safety_level=safety_level,
        recommendation_level=recommendation_level,
        moderation_status="MANUAL" if source == "MANUAL" else "SUCCEEDED",
        moderation_reason=decision.reason,
    )

    if ct in ("comment", "space_post"):
        content.is_recommended = recommendation_level == "RECOMMENDED"  # type: ignore[union-attr]

    if safety_level == "DANGEROUS" and not _is_user_deleted(content, ct):
        _apply_dangerous_action(content, ct)
        await create_notification(
            db,
            recipient_id=owner_id,
            actor_id=None,
            type=NotificationType.CONTENT_MODERATION,
            target_type=ct,
            target_id=content.id,
            extra={
                "action": "deleted" if ct in ("comment", "space_post") else "sanitized",
                "reason": decision.reason,
                "safety_level": safety_level,
                "source": source,
                "content_type": ct,
                "content_preview": _extract_content_preview(content, ct),
            },
        )

    history = ContentModerationHistory(
        content_type=ct,
        content_id=content.id,
        user_id=owner_id,
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
    ct = task.content_type
    terminal = task.attempt_count >= task.max_attempts
    if not terminal:
        task.status = "PENDING"
        task.available_at = _utcnow() + timedelta(
            seconds=2 ** (task.attempt_count - 1)
        )
        content = await _get_content(db, ct, task.content_id, for_update=True)
        if content is not None and _get_moderation_version(content, ct) == task.moderation_version:
            _set_moderation_fields(
                content,
                ct,
                safety_score=_get_safety_score(content, ct) or 0,
                recommendation_score=0,
                safety_level=_get_previous_safety_level(content, ct) or "SAFE",
                recommendation_level=_get_previous_recommendation_level(content, ct) or "NORMAL",
                moderation_status="PENDING",
                moderation_reason=task.last_error,
            )
        await db.commit()
        return False

    task.status = "FAILED"
    content = await _get_content(db, ct, task.content_id, for_update=True)
    if content is not None and _get_moderation_version(content, ct) == task.moderation_version:
        _set_moderation_fields(
            content,
            ct,
            safety_score=_get_safety_score(content, ct) or 0,
            recommendation_score=0,
            safety_level=_get_previous_safety_level(content, ct) or "SAFE",
            recommendation_level=_get_previous_recommendation_level(content, ct) or "NORMAL",
            moderation_status="FAILED",
            moderation_reason=task.last_error,
        )
        if not _is_user_deleted(content, ct):
            if ct in ("playlist", "user_profile"):
                _apply_dangerous_action(content, ct)
            else:
                content.is_deleted = True  # type: ignore[union-attr]
                content.deletion_reason = "MODERATION_FAILED"  # type: ignore[union-attr]
            await create_notification(
                db,
                recipient_id=_get_content_owner_id(content, ct),
                actor_id=None,
                type=NotificationType.CONTENT_MODERATION,
                target_type=ct,
                target_id=content.id,
                extra={
                    "action": "hidden_after_failures",
                    "reason": "自动审核连续失败，内容已暂时隐藏",
                    "source": "AGENT",
                    "content_type": ct,
                    "content_preview": _extract_content_preview(content, ct),
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
) -> Comment | SpacePost | Playlist | User:
    """恢复仅因自动审核而隐藏/清除的内容。

    对 comment/space_post：恢复 is_deleted 标记。
    对 playlist/user_profile：仅清除 deletion_reason，内容字段需由用户重新编辑。
    """
    content = await _get_content(db, content_type, content_id, for_update=True)
    if content is None:
        raise ValueError("content not found")

    if content_type == "user_profile":
        if content.profile_deletion_reason not in {  # type: ignore[union-attr]
            "MODERATION_DANGEROUS",
            "MODERATION_FAILED",
        }:
            raise ValueError("content was not deleted by moderation")
        content.profile_deletion_reason = None  # type: ignore[union-attr]
    elif content_type == "playlist":
        if content.deletion_reason not in {  # type: ignore[union-attr]
            "MODERATION_DANGEROUS",
            "MODERATION_FAILED",
        }:
            raise ValueError("content was not deleted by moderation")
        content.deletion_reason = None  # type: ignore[union-attr]
    else:
        if content.deletion_reason not in {  # type: ignore[union-attr]
            "MODERATION_DANGEROUS",
            "MODERATION_FAILED",
        }:
            raise ValueError("content was not deleted by moderation")
        content.is_deleted = False  # type: ignore[union-attr]
        content.deletion_reason = None  # type: ignore[union-attr]
    await db.commit()
    return content
