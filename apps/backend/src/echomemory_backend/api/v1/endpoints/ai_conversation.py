"""AI 对话相关的 API 路由端点。"""
from echomemory_backend.core.exceptions.codes import HttpStatus

import logging
from typing import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from echomemory_backend.api.deps import ActiveUser, PositiveIntPath, SessionDep
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.schemas.ai_conversation import (
    AIConversationCreate,
    AIConversationMessageRole,
    AIConversationMessageCreate,
    AIConversationMessagesOut,
    AIConversationOut,
    AIConversationTitleUpdate,
    AIConversationWithFirstMessageOut,
    AIStreamChunkOut,
    PaginatedAIConversationOut,
)
from echomemory_backend.services import ai_conversation_service

logger = logging.getLogger(__name__)

_USER_MESSAGE_TYPES: set[AIConversationMessageRole] = {"human", "ai"}


def _read_only_for_user(user: ActiveUser) -> bool:
    """根据用户状态判断是否只允许使用只读工具。"""
    return user.status in (UserStatus.MUTED, UserStatus.RESTRICTED)


def _resolve_message_view(
    role: int,
    requested_types: list[AIConversationMessageRole] | None,
) -> tuple[set[AIConversationMessageRole], bool]:
    """根据调用者角色解析会话历史视图。

    普通用户与 VIP 始终只能读取 human 和最终 ai 消息。管理员和超级管理员
    只有显式提供筛选类型时才能读取内部消息；未提供时仍使用安全默认视图。
    """
    is_admin = role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
    if not is_admin or requested_types is None:
        return set(_USER_MESSAGE_TYPES), False
    return set(requested_types), True


router = APIRouter(prefix="/ai/conversations", tags=["ai-conversations"])


def _format_sse(chunk: AIStreamChunkOut) -> str:
    """将流式数据包格式化为 SSE 行。"""
    return f"data: {chunk.model_dump_json()}\n\n"


async def _stream_response(
    stream: AsyncIterator[AIStreamChunkOut],
) -> AsyncIterator[str]:
    """将服务层流式迭代器转换为 SSE 文本流。"""
    try:
        async for chunk in stream:
            yield _format_sse(chunk)
    except Exception:
        logger.exception("AI stream response generator failed")
        yield _format_sse(
            AIStreamChunkOut(type="error", data="流式响应异常")
        )
        yield _format_sse(AIStreamChunkOut(type="done"))


@router.get("", response_model=PaginatedAIConversationOut)
async def list_ai_conversations(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出当前用户的 AI 对话会话。"""
    result = await ai_conversation_service.list_conversations(
        db, user_id=current_user.id, limit=limit, offset=offset
    )
    return PaginatedAIConversationOut(items=result["items"], total=result["total"])


@router.post("", response_model=AIConversationWithFirstMessageOut, status_code=HttpStatus.CREATED)
async def create_ai_conversation(
    db: SessionDep,
    current_user: ActiveUser,
    data: AIConversationCreate,
):
    """创建新的 AI 对话会话。

    若请求体包含 ``first_message`` 且 ``stream=False``，则自动发送该消息并返回 AI 首条回复。
    若 ``stream=True`` 且 ``first_message`` 非空，则以 ``text/event-stream`` 格式流式返回首条回复；
    首个 content chunk 的 ``meta.conversation`` 携带会话元数据。
    """
    read_only = _read_only_for_user(current_user)
    if data.stream and data.first_message:
        stream = ai_conversation_service.stream_first_message(
            db,
            user_id=current_user.id,
            actor_username=current_user.username,
            title=data.title,
            model=data.model,
            content=data.first_message,
            read_only=read_only,
        )
        return StreamingResponse(
            _stream_response(stream),
            media_type="text/event-stream",
        )

    conversation, ai_message = await ai_conversation_service.create_conversation(
        db,
        user_id=current_user.id,
        actor_username=current_user.username,
        title=data.title,
        model=data.model,
        first_message=data.first_message,
        read_only=read_only,
    )
    return AIConversationWithFirstMessageOut(
        conversation=AIConversationOut.model_validate(conversation),
        ai_message=ai_message,
    )


@router.get("/{conversation_id}/messages", response_model=AIConversationMessagesOut)
async def list_ai_messages(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: PositiveIntPath,
    message_types: list[AIConversationMessageRole] | None = Query(default=None),
):
    """获取指定 AI 会话的消息列表。

    普通用户与 VIP 仅返回 human 和最终 ai 消息。管理员与超级管理员可通过
    ``message_types`` 重复查询参数筛选 system、human、ai、tool 消息。
    """
    conversation = await ai_conversation_service.get_conversation(
        db, user_id=current_user.id, conversation_id=conversation_id
    )
    resolved_types, include_intermediate_ai = _resolve_message_view(
        current_user.role,
        message_types,
    )
    messages = await ai_conversation_service.get_messages(
        db,
        conversation=conversation,
        message_types=resolved_types,
        include_intermediate_ai=include_intermediate_ai,
    )
    return AIConversationMessagesOut(messages=messages)


@router.post("/{conversation_id}/messages")
async def send_ai_message(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: PositiveIntPath,
    data: AIConversationMessageCreate,
):
    """向指定 AI 会话发送消息。

    当 ``stream=True`` 时，以 ``text/event-stream`` 格式流式返回 AI 回复；
    否则返回完整的 AI 回复消息 JSON。
    """
    read_only = _read_only_for_user(current_user)
    conversation = await ai_conversation_service.get_conversation(
        db, user_id=current_user.id, conversation_id=conversation_id
    )

    if data.stream:
        stream = ai_conversation_service.stream_message(
            db,
            user_id=current_user.id,
            actor_username=current_user.username,
            conversation=conversation,
            content=data.content,
            read_only=read_only,
            confirmation_token=data.confirmation_token,
        )
        return StreamingResponse(
            _stream_response(stream),
            media_type="text/event-stream",
        )

    ai_message = await ai_conversation_service.send_message(
        db,
        user_id=current_user.id,
        actor_username=current_user.username,
        conversation=conversation,
        content=data.content,
        read_only=read_only,
        confirmation_token=data.confirmation_token,
    )
    return ai_message


@router.patch("/{conversation_id}", response_model=AIConversationOut)
async def update_ai_conversation_title(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: PositiveIntPath,
    data: AIConversationTitleUpdate,
):
    """手动更新指定 AI 会话的标题。"""
    conversation = await ai_conversation_service.get_conversation(
        db, user_id=current_user.id, conversation_id=conversation_id
    )
    updated = await ai_conversation_service.update_conversation_title(
        db, user_id=current_user.id, conversation=conversation, title=data.title
    )
    return AIConversationOut.model_validate(updated)


@router.delete("/{conversation_id}", status_code=HttpStatus.NO_CONTENT)
async def delete_ai_conversation(
    db: SessionDep,
    current_user: ActiveUser,
    conversation_id: PositiveIntPath,
):
    """软删除指定 AI 会话。"""
    conversation = await ai_conversation_service.get_conversation(
        db, user_id=current_user.id, conversation_id=conversation_id
    )
    await ai_conversation_service.delete_conversation(
        db, user_id=current_user.id, conversation=conversation
    )
    return None
