"""私信会话与消息相关的 API 路由端点。"""

from fastapi import APIRouter, Query, status

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.models.message import Conversation
from echomemory_backend.models.user import User
from echomemory_backend.schemas.message import (
    ConversationOut,
    DirectMessageCreate,
    DirectMessageOut,
    MessagePeerOut,
    PaginatedConversationOut,
    PaginatedDirectMessageOut,
)
from echomemory_backend.services import message_service

router = APIRouter(prefix="/messages", tags=["messages"])


def _peer_user(conversation: Conversation, viewer_id: int) -> User:
    """根据当前用户取出会话中的对端 User 实例。

    Args:
        conversation: 已 selectinload user1 / user2 的会话实例。
        viewer_id: 当前用户主键。

    Returns:
        对端 User 实例。
    """
    return conversation.user2 if conversation.user1_id == viewer_id else conversation.user1


def _unread_for(conversation: Conversation, viewer_id: int) -> int:
    """取出会话中当前用户的未读数。

    Args:
        conversation: 会话实例。
        viewer_id: 当前用户主键。

    Returns:
        当前用户未读数。
    """
    return (
        conversation.user1_unread_count
        if conversation.user1_id == viewer_id
        else conversation.user2_unread_count
    )


async def _build_conversation_out(
    db,
    conversation: Conversation,
    viewer_id: int,
    *,
    block_states: dict[int, tuple[bool, bool]] | None = None,
) -> ConversationOut:
    """将会话 ORM 实例转换为含对端信息、未读数、屏蔽态的 ConversationOut。

    Args:
        db: SQLAlchemy 异步 Session。
        conversation: 已 selectinload 关联的会话实例。
        viewer_id: 当前用户主键。
        block_states: 可选的批量屏蔽状态缓存；未提供时单独查询。

    Returns:
        ConversationOut 实例。
    """
    peer = _peer_user(conversation, viewer_id)
    if block_states is None:
        is_blocked_by_me, is_blocking_me = await message_service.get_block_state(
            db, viewer_id=viewer_id, peer_id=peer.id
        )
    else:
        is_blocked_by_me, is_blocking_me = block_states.get(peer.id, (False, False))
    last_message = (
        DirectMessageOut.model_validate(conversation.last_message)
        if conversation.last_message is not None
        else None
    )
    return ConversationOut(
        id=conversation.id,
        peer=MessagePeerOut.model_validate(peer),
        last_message=last_message,
        unread_count=_unread_for(conversation, viewer_id),
        is_blocked_by_me=is_blocked_by_me,
        is_blocking_me=is_blocking_me,
        updated_at=conversation.updated_at,
    )


@router.get("/conversations", response_model=PaginatedConversationOut)
async def list_conversations(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出当前用户的私信会话，按最近活跃倒序。"""
    result = await message_service.list_conversations(
        db, user_id=current_user.id, limit=limit, offset=offset
    )
    peer_ids = [_peer_user(conv, current_user.id).id for conv in result["items"]]
    block_states = await message_service.get_block_states_batch(
        db, viewer_id=current_user.id, peer_ids=peer_ids
    )
    items = [
        await _build_conversation_out(
            db, conv, current_user.id, block_states=block_states
        )
        for conv in result["items"]
    ]
    return PaginatedConversationOut(items=items, total=result["total"])


@router.get("/conversations/with/{user_id}", response_model=ConversationOut)
async def get_or_init_conversation(
    db: SessionDep,
    current_user: ActiveUser,
    user_id: int,
):
    """获取与指定用户的会话元数据。会话不存在时返回 404，由发送首条消息时自动创建。"""
    if user_id == current_user.id:
        raise BusinessError("Cannot start a conversation with yourself", 400)
    conversation = await message_service.get_conversation_with_user(
        db, viewer_id=current_user.id, peer_id=user_id
    )
    if conversation is None:
        raise BusinessError("Conversation not found", 404)
    return await _build_conversation_out(db, conversation, current_user.id)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=PaginatedDirectMessageOut,
)
async def list_messages(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: int,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页拉取会话中的消息，按时间倒序返回。"""
    result = await message_service.list_messages(
        db,
        viewer_id=current_user.id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    items = [DirectMessageOut.model_validate(m) for m in result["items"]]
    return PaginatedDirectMessageOut(items=items, total=result["total"])


@router.post(
    "/conversations/{conversation_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_read(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: int,
):
    """将指定会话中当前用户的未读数清零。"""
    await message_service.mark_conversation_read(
        db, viewer_id=current_user.id, conversation_id=conversation_id
    )
    return None


@router.post(
    "/{user_id}",
    response_model=DirectMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    db: SessionDep,
    current_user: ActiveUser,
    user_id: int,
    data: DirectMessageCreate,
):
    """向指定用户发送私信，会话不存在时自动创建。"""
    message = await message_service.send_message(
        db,
        sender_id=current_user.id,
        recipient_id=user_id,
        content=data.content,
    )
    return DirectMessageOut.model_validate(message)
