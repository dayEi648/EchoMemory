"""管理员内容审核查询与操作服务。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.content_moderation import (
    UserContentModerationStats,
)
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User
from echomemory_backend.schemas.content_moderation import (
    AdminModeratedContentOut,
    ModerationDecision,
    UserContentModerationStatsOut,
)
from echomemory_backend.services.content_moderation_service import (
    apply_moderation_decision,
    enqueue_moderation,
    restore_moderation_deleted_content,
)

ContentType = Literal["comment", "space_post"]


def _escaped_pattern(query: str) -> str:
    """构造安全的 ILIKE 模式。"""
    escaped = (
        query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return f"%{escaped}%"


def _comment_target(comment: Comment) -> tuple[str | None, int | None]:
    """返回评论目标类型和 ID。"""
    if comment.music_id is not None:
        return "music", comment.music_id
    if comment.playlist_id is not None:
        return "playlist", comment.playlist_id
    if comment.space_post_id is not None:
        return "space_post", comment.space_post_id
    return None, None


def _to_out(
    content_type: ContentType,
    content: Comment | SpacePost,
    username: str,
) -> AdminModeratedContentOut:
    """把 ORM 内容转换为统一管理输出。"""
    target_type, target_id = (
        _comment_target(content) if isinstance(content, Comment) else (None, None)
    )
    return AdminModeratedContentOut(
        id=content.id,
        content_type=content_type,
        user_id=content.user_id,
        username=username,
        content=content.content,
        target_type=target_type,
        target_id=target_id,
        safety_score=content.safety,
        recommendation_score=content.recommendation_score,
        safety_level=content.safety_level,
        recommendation_level=content.recommendation_level,
        moderation_status=content.moderation_status,
        moderation_reason=content.moderation_reason,
        is_recommended=content.is_recommended,
        is_deleted=content.is_deleted,
        deletion_reason=content.deletion_reason,
        moderated_at=content.moderated_at,
        created_at=content.created_at,
    )


async def list_moderated_content(
    db: AsyncSession,
    *,
    content_type: ContentType,
    q: str | None = None,
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    safety_level: str | None = None,
    recommendation_level: str | None = None,
    moderation_status: str | None = None,
    is_deleted: bool | None = None,
    is_recommended: bool | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AdminModeratedContentOut], int]:
    """按管理筛选条件分页查询评论或空间动态。"""
    model = Comment if content_type == "comment" else SpacePost
    filters = []
    if q:
        pattern = _escaped_pattern(q)
        filters.append(
            or_(
                model.content.ilike(pattern, escape="\\"),
                User.username.ilike(pattern, escape="\\"),
                User.nickname.ilike(pattern, escape="\\"),
            )
        )
    if user_id is not None:
        filters.append(model.user_id == user_id)
    if safety_level:
        filters.append(model.safety_level == safety_level)
    if recommendation_level:
        filters.append(model.recommendation_level == recommendation_level)
    if moderation_status:
        filters.append(model.moderation_status == moderation_status)
    if is_deleted is not None:
        filters.append(model.is_deleted.is_(is_deleted))
    if is_recommended is not None:
        filters.append(model.is_recommended.is_(is_recommended))
    if start_time:
        filters.append(model.created_at >= start_time)
    if end_time:
        filters.append(model.created_at <= end_time)

    if content_type == "comment":
        target_columns = {
            "music": Comment.music_id,
            "playlist": Comment.playlist_id,
            "space_post": Comment.space_post_id,
        }
        if target_type:
            column = target_columns.get(target_type)
            if column is None:
                raise BusinessError(
                    "无效的评论目标类型",
                    code=ErrorCode.CLIENT_INVALID_TARGET_TYPE,
                )
            filters.append(column.is_not(None))
            if target_id is not None:
                filters.append(column == target_id)
        elif target_id is not None:
            filters.append(
                or_(
                    Comment.music_id == target_id,
                    Comment.playlist_id == target_id,
                    Comment.space_post_id == target_id,
                )
            )

    base = select(model, User.username).join(User, User.id == model.user_id)
    count_stmt = (
        select(func.count())
        .select_from(model)
        .join(User, User.id == model.user_id)
        .where(*filters)
    )
    rows = (
        await db.execute(
            base.where(*filters)
            .order_by(model.created_at.desc(), model.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = (await db.execute(count_stmt)).scalar_one()
    return [
        _to_out(content_type, content, username)
        for content, username in rows
    ], total


async def get_moderated_content(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
) -> AdminModeratedContentOut:
    """获取单条管理内容。"""
    model = Comment if content_type == "comment" else SpacePost
    row = (
        await db.execute(
            select(model, User.username)
            .join(User, User.id == model.user_id)
            .where(model.id == content_id)
        )
    ).one_or_none()
    if row is None:
        raise BusinessError(
            "内容不存在", code=ErrorCode.RESOURCE_NOT_FOUND
        )
    return _to_out(content_type, row[0], row[1])


async def request_rereview(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
) -> AdminModeratedContentOut:
    """创建新版本审核任务。"""
    try:
        await enqueue_moderation(
            db,
            content_type=content_type,
            content_id=content_id,
            force=True,
            commit=True,
        )
    except ValueError as exc:
        raise BusinessError(
            "内容不存在", code=ErrorCode.RESOURCE_NOT_FOUND
        ) from exc
    return await get_moderated_content(
        db, content_type=content_type, content_id=content_id
    )


async def apply_manual_review(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
    reviewer_user_id: int,
    decision: ModerationDecision,
) -> AdminModeratedContentOut:
    """管理员创建新版本并立即应用人工审核结果。"""
    try:
        task = await enqueue_moderation(
            db,
            content_type=content_type,
            content_id=content_id,
            force=True,
            commit=True,
        )
    except ValueError as exc:
        raise BusinessError(
            "内容不存在", code=ErrorCode.RESOURCE_NOT_FOUND
        ) from exc
    await apply_moderation_decision(
        db,
        task=task,
        decision=decision,
        source="MANUAL",
        reviewer_user_id=reviewer_user_id,
    )
    return await get_moderated_content(
        db, content_type=content_type, content_id=content_id
    )


async def restore_content(
    db: AsyncSession,
    *,
    content_type: ContentType,
    content_id: int,
) -> AdminModeratedContentOut:
    """恢复因审核隐藏的内容。"""
    try:
        await restore_moderation_deleted_content(
            db,
            content_type=content_type,
            content_id=content_id,
        )
    except ValueError as exc:
        message = str(exc)
        code = (
            ErrorCode.RESOURCE_NOT_FOUND
            if message == "content not found"
            else ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS
        )
        raise BusinessError(message, code=code) from exc
    return await get_moderated_content(
        db, content_type=content_type, content_id=content_id
    )


async def get_user_stats(
    db: AsyncSession, user_id: int
) -> UserContentModerationStatsOut:
    """获取用户审核结果聚合统计。"""
    user_exists = await db.scalar(select(User.id).where(User.id == user_id))
    if user_exists is None:
        raise BusinessError(
            "用户不存在", code=ErrorCode.USER_NOT_FOUND
        )
    stats = await db.get(UserContentModerationStats, user_id)
    if stats is None:
        return UserContentModerationStatsOut(
            user_id=user_id,
            risky_count=0,
            dangerous_count=0,
            recommended_count=0,
            updated_at=datetime.now().astimezone(),
        )
    return UserContentModerationStatsOut.model_validate(
        stats, from_attributes=True
    )
