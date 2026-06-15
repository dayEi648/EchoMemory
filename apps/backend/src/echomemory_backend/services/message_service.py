"""私信业务服务模块，提供会话查询/创建、消息发送/分页、用户屏蔽等核心操作。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

import logging

from sqlalchemy import and_, desc, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.inbox.pubsub import publish_inbox_event
from echomemory_backend.models.message import Conversation, DirectMessage, UserBlock
from echomemory_backend.models.user import User

logger = logging.getLogger(__name__)


def _ordered_pair(a: int, b: int) -> tuple[int, int]:
    """将两个用户主键归一化为 (min, max) 顺序，对应 conversations 的 user1_id < user2_id。

    Args:
        a: 第一个用户主键。
        b: 第二个用户主键。

    Returns:
        (min(a, b), max(a, b)) 元组。
    """
    return (a, b) if a < b else (b, a)


async def _get_conversation_pair(
    db: AsyncSession, user_a: int, user_b: int
) -> Conversation | None:
    """根据无序的两个用户主键查询会话。

    Args:
        db: SQLAlchemy 异步 Session。
        user_a: 任一用户主键。
        user_b: 另一用户主键。

    Returns:
        Conversation 实例，不存在时返回 None。
    """
    u1, u2 = _ordered_pair(user_a, user_b)
    stmt = select(Conversation).where(
        Conversation.user1_id == u1,
        Conversation.user2_id == u2,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_or_create_conversation(
    db: AsyncSession, user_a: int, user_b: int
) -> Conversation:
    """获取或创建会话。已存在时直接返回；不存在时插入并使用 ON CONFLICT 防并发重复。

    Args:
        db: SQLAlchemy 异步 Session。
        user_a: 任一用户主键。
        user_b: 另一用户主键。

    Returns:
        会话 ORM 实例。
    """
    existing = await _get_conversation_pair(db, user_a, user_b)
    if existing is not None:
        return existing

    u1, u2 = _ordered_pair(user_a, user_b)
    stmt = (
        pg_insert(Conversation)
        .values(user1_id=u1, user2_id=u2)
        .on_conflict_do_nothing(constraint="uq_conversations_user_pair")
        .returning(Conversation.id)
    )
    inserted_id = (await db.execute(stmt)).scalar_one_or_none()
    if inserted_id is None:
        # 并发场景下被另一事务抢先插入，回查
        existing = await _get_conversation_pair(db, user_a, user_b)
        if existing is None:
            raise BusinessError("Failed to create conversation", code=ErrorCode.SYSTEM_CONVERSATION_CREATE_FAILED)
        return existing
    await db.flush()
    conversation = await db.get(Conversation, inserted_id)
    if conversation is None:
        raise BusinessError("Failed to create conversation", code=ErrorCode.SYSTEM_CONVERSATION_CREATE_FAILED)
    return conversation


async def is_blocked(db: AsyncSession, blocker_id: int, blocked_id: int) -> bool:
    """检查 blocker 是否屏蔽了 blocked。

    Args:
        db: SQLAlchemy 异步 Session。
        blocker_id: 屏蔽方主键。
        blocked_id: 被屏蔽方主键。

    Returns:
        已屏蔽返回 True，否则 False。
    """
    return (
        await db.execute(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
        )
    ).scalar_one_or_none() is not None


def _is_unique_violation(exc: IntegrityError) -> bool:
    """判断 IntegrityError 是否为唯一约束冲突。

    Args:
        exc: SQLAlchemy IntegrityError。

    Returns:
        唯一约束冲突返回 True，否则 False。
    """
    orig = exc.orig
    return orig is not None and getattr(orig, "pgcode", None) == "23505"


async def block_user(db: AsyncSession, blocker_id: int, blocked_id: int) -> None:
    """屏蔽用户（幂等）。

    Args:
        db: SQLAlchemy 异步 Session。
        blocker_id: 屏蔽方主键。
        blocked_id: 被屏蔽方主键。

    Returns:
        None。

    Raises:
        BusinessError: 自我屏蔽或目标用户不存在时抛出 400/404。
        IntegrityError: 非唯一约束的数据库完整性错误时重新抛出。
    """
    if blocker_id == blocked_id:
        raise BusinessError("Cannot block yourself", code=ErrorCode.CANNOT_BLOCK_SELF)
    target = await db.get(User, blocked_id)
    if target is None or target.is_deleted:
        raise BusinessError("User not found", code=ErrorCode.USER_NOT_FOUND)

    db.add(UserBlock(blocker_id=blocker_id, blocked_id=blocked_id))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_unique_violation(exc):
            return
        raise


async def unblock_user(db: AsyncSession, blocker_id: int, blocked_id: int) -> None:
    """取消屏蔽（幂等）。

    Args:
        db: SQLAlchemy 异步 Session。
        blocker_id: 屏蔽方主键。
        blocked_id: 被屏蔽方主键。

    Returns:
        None。
    """
    existing = await db.get(UserBlock, (blocker_id, blocked_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def send_message(
    db: AsyncSession,
    *,
    sender_id: int,
    recipient_id: int,
    content: str,
) -> DirectMessage:
    """发送私信，自动 upsert 会话并维护未读数与最后一条消息缓存。

    Args:
        db: SQLAlchemy 异步 Session。
        sender_id: 发送者主键。
        recipient_id: 接收者主键。
        content: 消息文本，schema 层已限定 1~2000 字符。

    Returns:
        新创建的 DirectMessage 实例。

    Raises:
        BusinessError: 自我发送、目标用户不存在或被对方屏蔽时抛出 400/403/404。
    """
    if sender_id == recipient_id:
        raise BusinessError("Cannot send message to yourself", code=ErrorCode.MESSAGE_CANNOT_TO_SELF)
    recipient = await db.get(User, recipient_id)
    if recipient is None or recipient.is_deleted:
        raise BusinessError("Recipient not found", code=ErrorCode.MESSAGE_RECIPIENT_NOT_FOUND)
    if await is_blocked(db, recipient_id, sender_id):
        raise BusinessError("You have been blocked by this user", code=ErrorCode.BLOCKED_BY_USER)

    conversation = await _get_or_create_conversation(db, sender_id, recipient_id)

    message = DirectMessage(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    await db.flush()

    unread_field = (
        Conversation.user2_unread_count
        if conversation.user1_id == sender_id
        else Conversation.user1_unread_count
    )
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation.id)
        .values(
            last_message_id=message.id,
            **{unread_field.key: unread_field + 1},
        )
    )
    await db.commit()
    await db.refresh(message)

    try:
        await publish_inbox_event(
            recipient_id,
            {
                "type": "message",
                "conversation_id": conversation.id,
                "message_id": message.id,
                "sender_id": sender_id,
                "content": message.content,
            },
        )
    except Exception:
        logger.exception("Failed to publish inbox event for message %s", message.id)
    return message


async def list_conversations(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    """列出当前用户参与的会话，按最近活跃倒序。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 当前用户主键。
        limit: 返回数量上限，默认 30。
        offset: 偏移量，默认 0。

    Returns:
        {"items": Conversation 列表（含 last_message 与 user1/user2 关联）, "total": 总记录数}。
    """
    where_clause = or_(
        Conversation.user1_id == user_id,
        Conversation.user2_id == user_id,
    )
    stmt = (
        select(Conversation)
        .where(where_clause)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(Conversation.user1),
            selectinload(Conversation.user2),
            selectinload(Conversation.last_message),
        )
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count()).select_from(Conversation).where(where_clause)
        )
    ).scalar_one()
    return {"items": items, "total": total}


async def get_conversation_with_user(
    db: AsyncSession, *, viewer_id: int, peer_id: int
) -> Conversation | None:
    """获取当前用户与指定对端的会话（含关联）。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_id: 查看者主键。
        peer_id: 对端用户主键。

    Returns:
        Conversation 实例，不存在时返回 None。
    """
    u1, u2 = _ordered_pair(viewer_id, peer_id)
    stmt = (
        select(Conversation)
        .where(Conversation.user1_id == u1, Conversation.user2_id == u2)
        .options(
            selectinload(Conversation.user1),
            selectinload(Conversation.user2),
            selectinload(Conversation.last_message),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_messages(
    db: AsyncSession,
    *,
    viewer_id: int,
    conversation_id: int,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, object]:
    """分页列出指定会话内的消息（按时间倒序）。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_id: 当前用户主键。
        conversation_id: 会话主键。
        limit: 返回数量上限，默认 30。
        offset: 偏移量，默认 0。

    Returns:
        {"items": DirectMessage 列表, "total": 总记录数}。

    Raises:
        BusinessError: 会话不存在或当前用户不属于该会话时抛出 404。
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or viewer_id not in (
        conversation.user1_id,
        conversation.user2_id,
    ):
        raise BusinessError("Conversation not found", code=ErrorCode.MESSAGE_CONVERSATION_NOT_FOUND)

    where_clause = DirectMessage.conversation_id == conversation_id
    stmt = (
        select(DirectMessage)
        .where(where_clause)
        .order_by(desc(DirectMessage.created_at))
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count()).select_from(DirectMessage).where(where_clause)
        )
    ).scalar_one()
    return {"items": items, "total": total}


async def mark_conversation_read(
    db: AsyncSession, *, viewer_id: int, conversation_id: int
) -> None:
    """将指定会话内当前用户的未读数清零。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_id: 当前用户主键。
        conversation_id: 会话主键。

    Returns:
        None。

    Raises:
        BusinessError: 会话不存在或当前用户不属于该会话时抛出 404。
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or viewer_id not in (
        conversation.user1_id,
        conversation.user2_id,
    ):
        raise BusinessError("Conversation not found", code=ErrorCode.MESSAGE_CONVERSATION_NOT_FOUND)

    field = (
        Conversation.user1_unread_count
        if conversation.user1_id == viewer_id
        else Conversation.user2_unread_count
    )
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values({field.key: 0})
    )
    await db.commit()


async def total_unread_messages(db: AsyncSession, user_id: int) -> int:
    """统计当前用户在所有会话中的未读私信总数。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 当前用户主键。

    Returns:
        全部会话累计未读数。
    """
    user1_total = (
        await db.execute(
            select(func.coalesce(func.sum(Conversation.user1_unread_count), 0)).where(
                Conversation.user1_id == user_id
            )
        )
    ).scalar_one()
    user2_total = (
        await db.execute(
            select(func.coalesce(func.sum(Conversation.user2_unread_count), 0)).where(
                Conversation.user2_id == user_id
            )
        )
    ).scalar_one()
    return int(user1_total) + int(user2_total)


async def get_block_states_batch(
    db: AsyncSession, *, viewer_id: int, peer_ids: list[int]
) -> dict[int, tuple[bool, bool]]:
    """批量获取 viewer 与多个对端用户的双向屏蔽状态。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_id: 当前用户主键。
        peer_ids: 对端用户主键列表。

    Returns:
        映射 peer_id -> (is_blocked_by_me, is_blocking_me)。
    """
    unique_peers = {peer_id for peer_id in peer_ids if peer_id != viewer_id}
    if not unique_peers:
        return {}

    rows = (
        await db.execute(
            select(UserBlock.blocker_id, UserBlock.blocked_id).where(
                or_(
                    and_(
                        UserBlock.blocker_id == viewer_id,
                        UserBlock.blocked_id.in_(unique_peers),
                    ),
                    and_(
                        UserBlock.blocker_id.in_(unique_peers),
                        UserBlock.blocked_id == viewer_id,
                    ),
                )
            )
        )
    ).all()

    states = {peer_id: (False, False) for peer_id in unique_peers}
    for row in rows:
        if row.blocker_id == viewer_id:
            blocked_by_me, blocking_me = states[row.blocked_id]
            states[row.blocked_id] = (True, blocking_me)
        else:
            blocked_by_me, blocking_me = states[row.blocker_id]
            states[row.blocker_id] = (blocked_by_me, True)
    return states


async def get_block_state(
    db: AsyncSession, *, viewer_id: int, peer_id: int
) -> tuple[bool, bool]:
    """获取双向屏蔽状态。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_id: 当前用户主键。
        peer_id: 对端用户主键。

    Returns:
        (is_blocked_by_me, is_blocking_me) 元组。
    """
    states = await get_block_states_batch(
        db, viewer_id=viewer_id, peer_ids=[peer_id]
    )
    return states.get(peer_id, (False, False))
