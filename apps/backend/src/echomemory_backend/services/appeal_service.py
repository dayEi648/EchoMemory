"""内容申诉服务 — 用户发起申诉、管理员处理。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.models.content_appeal import ContentAppeal
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.schemas.content_appeal import AppealCreate, AppealOut
from echomemory_backend.services.content_moderation_service import (
    ContentType,
    _get_moderation_version,
    _get_content,
    restore_moderation_deleted_content,
)
from echomemory_backend.services.notification_service import create_notification

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_appeal(
    db: AsyncSession,
    *,
    user_id: int,
    appeal_in: AppealCreate,
) -> AppealOut:
    """用户对审核决定发起申诉。

    同一内容同一审核版本只能有一个待处理申诉。
    """
    ct: ContentType = appeal_in.content_type  # type: ignore[assignment]
    content = await _get_content(db, ct, appeal_in.content_id, for_update=False)
    if content is None:
        raise BusinessError("内容不存在", code=ErrorCode.RESOURCE_NOT_FOUND)

    version = _get_moderation_version(content, ct)

    # 检查是否已有待处理申诉
    existing = (
        await db.execute(
            select(ContentAppeal).where(
                ContentAppeal.content_type == ct,
                ContentAppeal.content_id == appeal_in.content_id,
                ContentAppeal.moderation_version == version,
                ContentAppeal.status == "PENDING",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise BusinessError(
            "该内容已有待处理的申诉", code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS
        )

    appeal = ContentAppeal(
        content_type=ct,
        content_id=appeal_in.content_id,
        user_id=user_id,
        moderation_version=version,
        appeal_reason=appeal_in.appeal_reason,
    )
    db.add(appeal)
    await db.commit()
    await db.refresh(appeal)
    return AppealOut.model_validate(appeal)


async def list_appeals(
    db: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AppealOut], int]:
    """管理员分页查询申诉列表。"""
    from sqlalchemy import func

    filters = []
    if status:
        filters.append(ContentAppeal.status == status)

    count_stmt = select(func.count()).select_from(ContentAppeal).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(ContentAppeal)
        .where(*filters)
        .order_by(
            # PENDING 优先
            desc(ContentAppeal.status == "PENDING"),
            desc(ContentAppeal.created_at),
        )
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    return [AppealOut.model_validate(a) for a in items], total


async def approve_appeal(
    db: AsyncSession,
    *,
    appeal_id: int,
    reviewer_user_id: int,
    admin_note: str | None = None,
) -> AppealOut:
    """管理员批准申诉 — 恢复内容并通知用户。"""
    appeal = await db.get(ContentAppeal, appeal_id)
    if appeal is None:
        raise BusinessError("申诉不存在", code=ErrorCode.RESOURCE_NOT_FOUND)
    if appeal.status != "PENDING":
        raise BusinessError("申诉已处理", code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS)

    # 恢复内容
    try:
        await restore_moderation_deleted_content(
            db,
            content_type=appeal.content_type,  # type: ignore[arg-type]
            content_id=appeal.content_id,
        )
    except ValueError as exc:
        raise BusinessError(str(exc), code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS) from exc

    appeal.status = "APPROVED"
    appeal.reviewer_user_id = reviewer_user_id
    appeal.admin_note = admin_note
    appeal.resolved_at = _utcnow()
    await db.commit()
    await db.refresh(appeal)

    # 通知用户
    await create_notification(
        db,
        recipient_id=appeal.user_id,
        actor_id=None,
        type=NotificationType.CONTENT_MODERATION,
        target_type=appeal.content_type,
        target_id=appeal.content_id,
        extra={
            "action": "appeal_approved",
            "reason": "管理员已批准你的申诉，内容已恢复。",
            "source": "MANUAL",
            "content_type": appeal.content_type,
            "content_preview": "",
        },
    )
    return AppealOut.model_validate(appeal)


async def deny_appeal(
    db: AsyncSession,
    *,
    appeal_id: int,
    reviewer_user_id: int,
    admin_note: str | None = None,
) -> AppealOut:
    """管理员驳回申诉 — 维持审核决定并通知用户。"""
    appeal = await db.get(ContentAppeal, appeal_id)
    if appeal is None:
        raise BusinessError("申诉不存在", code=ErrorCode.RESOURCE_NOT_FOUND)
    if appeal.status != "PENDING":
        raise BusinessError("申诉已处理", code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS)

    appeal.status = "DENIED"
    appeal.reviewer_user_id = reviewer_user_id
    appeal.admin_note = admin_note
    appeal.resolved_at = _utcnow()
    await db.commit()
    await db.refresh(appeal)

    note = f"：{admin_note}" if admin_note else ""
    await create_notification(
        db,
        recipient_id=appeal.user_id,
        actor_id=None,
        type=NotificationType.CONTENT_MODERATION,
        target_type=appeal.content_type,
        target_id=appeal.content_id,
        extra={
            "action": "appeal_denied",
            "reason": f"管理员驳回了你的申诉，审核决定维持不变{note}",
            "source": "MANUAL",
            "content_type": appeal.content_type,
            "content_preview": "",
        },
    )
    return AppealOut.model_validate(appeal)
