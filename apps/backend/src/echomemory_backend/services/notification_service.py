"""通知业务服务模块，提供通知的创建（幂等）、查询、未读统计与已读标记等核心操作。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

import logging

from sqlalchemy import desc, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.inbox.pubsub import publish_inbox_event
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncSession,
    *,
    recipient_id: int,
    actor_id: int | None,
    type: NotificationType,
    target_type: str,
    target_id: int,
    extra: dict | None = None,
) -> Notification | None:
    """幂等创建通知并向 Inbox Pub/Sub 频道广播事件。

    若 (recipient, actor, type, target) 已存在未读通知，则不再次入库并返回 None；
    自我事件（actor == recipient）一律忽略并返回 None。
    本函数不会自行 commit，由调用方在合适的事务边界内提交，确保业务行为与通知同生共死。

    Args:
        db: SQLAlchemy 异步 Session。
        recipient_id: 通知接收者主键。
        actor_id: 触发事件的用户主键，系统通知时为 None。
        type: 通知类型枚举。
        target_type: 目标实体类型（user / comment / space_post）。
        target_id: 目标实体主键。
        extra: 冗余上下文（如评论内容预览），方便前端展示，默认空 dict。

    Returns:
        新创建的 Notification 实例；若被幂等约束去重则返回 None。

    Raises:
        BusinessError: target_type 非法时抛出 400。
    """
    if target_type not in ("user", "comment", "space_post"):
        raise BusinessError("Invalid target_type", code=ErrorCode.CLIENT_INVALID_TARGET_TYPE)
    if actor_id is not None and actor_id == recipient_id:
        return None

    payload = {
        "recipient_id": recipient_id,
        "actor_id": actor_id,
        "type": int(type),
        "target_type": target_type,
        "target_id": target_id,
        "is_read": False,
        "extra": extra or {},
    }
    if actor_id is not None:
        conflict_elements = [
            Notification.recipient_id,
            Notification.actor_id,
            Notification.type,
            Notification.target_type,
            Notification.target_id,
        ]
        conflict_where = text("is_read = false AND actor_id IS NOT NULL")
    else:
        conflict_elements = [
            Notification.recipient_id,
            Notification.type,
            Notification.target_type,
            Notification.target_id,
        ]
        conflict_where = text("is_read = false AND actor_id IS NULL")

    stmt = (
        pg_insert(Notification)
        .values(**payload)
        .on_conflict_do_nothing(
            index_elements=conflict_elements,
            index_where=conflict_where,
        )
        .returning(Notification.id)
    )
    inserted_id = (await db.execute(stmt)).scalar_one_or_none()
    if inserted_id is None:
        return None
    await db.flush()

    notification = (
        await db.execute(
            select(Notification)
            .where(Notification.id == inserted_id)
            .options(selectinload(Notification.actor))
        )
    ).scalar_one()

    try:
        await publish_inbox_event(
            recipient_id,
            {
                "type": "notification",
                "id": notification.id,
                "notification_type": int(type),
                "target_type": target_type,
                "target_id": target_id,
            },
        )
    except Exception:
        # 推送失败不影响通知落库；客户端会通过未读汇总轮询补齐
        logger.exception("Failed to publish inbox event for notification %s", inserted_id)
    return notification


async def list_notifications(
    db: AsyncSession,
    *,
    recipient_id: int,
    limit: int = 20,
    offset: int = 0,
    only_unread: bool = False,
) -> dict[str, object]:
    """按时间倒序分页查询通知。

    Args:
        db: SQLAlchemy 异步 Session。
        recipient_id: 接收者主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。
        only_unread: 仅返回未读，默认 False。

    Returns:
        {"items": Notification 列表, "total": 总记录数}。
    """
    where_clause = [Notification.recipient_id == recipient_id]
    if only_unread:
        where_clause.append(Notification.is_read.is_(False))

    stmt = (
        select(Notification)
        .where(*where_clause)
        .order_by(desc(Notification.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(Notification.actor))
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).select_from(Notification).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


async def count_unread_notifications(db: AsyncSession, recipient_id: int) -> int:
    """查询当前用户未读通知数。

    Args:
        db: SQLAlchemy 异步 Session。
        recipient_id: 接收者主键。

    Returns:
        未读通知数。
    """
    return (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.is_read.is_(False),
            )
        )
    ).scalar_one()


async def mark_notification_read(
    db: AsyncSession, *, recipient_id: int, notification_id: int
) -> None:
    """将单条通知标记为已读。

    Args:
        db: SQLAlchemy 异步 Session。
        recipient_id: 当前用户主键。
        notification_id: 通知主键。

    Returns:
        None。

    Raises:
        BusinessError: 通知不存在或不属于当前用户时抛出 404。
    """
    notification = await db.get(Notification, notification_id)
    if notification is None or notification.recipient_id != recipient_id:
        raise BusinessError("Notification not found", code=ErrorCode.NOTIFICATION_NOT_FOUND)
    if notification.is_read:
        return
    notification.is_read = True
    await db.commit()


async def mark_all_notifications_read(db: AsyncSession, recipient_id: int) -> int:
    """将当前用户的全部未读通知标记为已读。

    Args:
        db: SQLAlchemy 异步 Session。
        recipient_id: 接收者主键。

    Returns:
        本次操作影响的通知数。
    """
    result = await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == recipient_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount or 0
