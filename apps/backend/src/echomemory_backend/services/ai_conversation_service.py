"""AI 对话业务服务模块。

提供会话创建、消息发送、消息列表查询、软删除等能力，
并负责维护 Redis 缓存与 LangGraph checkpoint 状态的一致性。
"""

from __future__ import annotations
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

import logging
from typing import Any, AsyncIterator

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.ai.graphs.conversation.builder import build_graph, get_thread_config
from echomemory_backend.ai.graphs.conversation import cache as ai_cache_module
from echomemory_backend.ai.graphs.conversation.prompts import get_system_prompt
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.models.ai_conversation import AIConversation, AIConversationStatus
from echomemory_backend.schemas.ai_conversation import (
    AIConversationMessageOut,
    AIConversationOut,
    AIStreamChunkOut,
)

logger = logging.getLogger(__name__)


def _message_to_dict(message: BaseMessage) -> dict[str, Any]:
    """将 LangChain 消息转换为 API 输出字典。

    参数:
        message: LangChain BaseMessage 实例。

    返回:
        包含 role、content、额外字段的字典。
    """
    role_map = {
        "system": "system",
        "human": "human",
        "ai": "ai",
        "tool": "tool",
    }
    role = role_map.get(message.type, "human")
    data: dict[str, Any] = {
        "role": role,
        "content": message.content,
        "additional_kwargs": dict(message.additional_kwargs),
    }
    if role == "ai":
        data["reasoning_content"] = message.additional_kwargs.get("reasoning_content")
    elif isinstance(message, ToolMessage):
        data["tool_call_id"] = message.tool_call_id
        data["name"] = message.name
    return data


def _messages_to_dicts(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """批量转换 LangChain 消息为 API 输出字典。

    参数:
        messages: LangChain BaseMessage 列表。

    返回:
        输出字典列表。
    """
    return [_message_to_dict(m) for m in messages]


def _build_ai_conversation_out(conversation: AIConversation) -> AIConversationOut:
    """将 AIConversation ORM 实例转换为输出 Schema。

    参数:
        conversation: AIConversation ORM 实例。

    返回:
        AIConversationOut 实例。
    """
    return AIConversationOut.model_validate(conversation)


async def create_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    title: str | None = None,
    model: str | None = None,
    first_message: str | None = None,
) -> tuple[AIConversation, AIConversationMessageOut | None]:
    """创建 AI 对话会话。

    创建业务元数据，并在 checkpoint 中初始化系统消息。
    若提供首条用户消息，则自动调用一次模型获取回复。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        title: 会话标题；None 时使用默认标题。
        model: 模型 ID；None 时使用配置默认模型。
        first_message: 首条用户消息；None 表示仅创建空会话。

    返回:
        (AIConversation 实例, 首条 AI 回复消息或 None)。
    """
    conversation = AIConversation(
        user_id=user_id,
        title=title or settings.ai_default_title,
        model=model or settings.ai_default_model,
        status=AIConversationStatus.ACTIVE,
        thread_id="",  # 临时值，flush 后用 id 回填
    )
    db.add(conversation)
    await db.flush()
    conversation.thread_id = str(conversation.id)
    await db.commit()
    await db.refresh(conversation)

    # 在 checkpoint 中写入系统消息，初始化对话状态
    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    await graph.ainvoke(
        {
            "messages": [SystemMessage(content=get_system_prompt())],
            "user_id": user_id,
        },
        config,
    )

    await ai_cache_module.invalidate_conversation_list(user_id)

    ai_reply: AIConversationMessageOut | None = None
    if first_message:
        ai_reply = await send_message(
            db, user_id=user_id, conversation=conversation, content=first_message
        )

    return conversation, ai_reply


async def list_conversations(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = 30,
    offset: int = 0,
    use_cache: bool = True,
) -> dict[str, Any]:
    """分页列出当前用户的 AI 会话。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限。
        offset: 偏移量。
        use_cache: 是否读取 Redis 缓存。

    返回:
        {"items": AIConversationOut 列表, "total": 总记录数}。
    """
    items: list[AIConversationOut] = []
    loaded_from_cache = False

    if use_cache and offset == 0:
        cached = await ai_cache_module.get_conversation_list(user_id)
        if cached is not None:
            items = [AIConversationOut(**item) for item in cached]
            loaded_from_cache = True

    if not loaded_from_cache:
        stmt = (
            select(AIConversation)
            .where(
                AIConversation.user_id == user_id,
                AIConversation.status == AIConversationStatus.ACTIVE,
            )
            .order_by(desc(AIConversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        items = [_build_ai_conversation_out(conv) for conv in result.scalars().all()]

    total_stmt = (
        select(func.count())
        .select_from(AIConversation)
        .where(
            AIConversation.user_id == user_id,
            AIConversation.status == AIConversationStatus.ACTIVE,
        )
    )
    total = (await db.execute(total_stmt)).scalar_one()

    if use_cache and offset == 0 and not loaded_from_cache:
        await ai_cache_module.set_conversation_list(user_id, [item.model_dump() for item in items])

    return {"items": items, "total": total}


async def get_conversation(
    db: AsyncSession, *, user_id: int, conversation_id: int
) -> AIConversation:
    """获取指定用户的 AI 会话。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        conversation_id: 会话主键。

    返回:
        AIConversation 实例。

    异常:
        BusinessError: 会话不存在、已删除或不属于当前用户时抛出 404。
    """
    conversation = await db.get(AIConversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise BusinessError("Conversation not found", code=ErrorCode.MESSAGE_CONVERSATION_NOT_FOUND)
    if conversation.status == AIConversationStatus.DELETED:
        raise BusinessError("Conversation not found", code=ErrorCode.MESSAGE_CONVERSATION_NOT_FOUND)
    return conversation


async def get_messages(
    db: AsyncSession,
    *,
    conversation: AIConversation,
    use_cache: bool = True,
) -> list[AIConversationMessageOut]:
    """获取会话消息列表。

    优先读取 Redis 缓存；未命中时从 LangGraph checkpoint 加载状态并回写缓存。

    参数:
        db: SQLAlchemy 异步 Session（兼容性参数，实际读取 checkpoint）。
        conversation: AIConversation 实例。
        use_cache: 是否读取 Redis 缓存。

    返回:
        AIConversationMessageOut 列表。
    """
    if use_cache:
        cached = await ai_cache_module.get_messages(conversation.id)
        if cached is not None:
            return [AIConversationMessageOut(**msg) for msg in cached]

    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    state = await graph.aget_state(config)
    messages = state.values.get("messages", []) if state else []
    message_dicts = _messages_to_dicts(messages)

    if use_cache:
        await ai_cache_module.set_messages(conversation.id, message_dicts)

    return [AIConversationMessageOut(**msg) for msg in message_dicts]


async def send_message(
    db: AsyncSession,
    *,
    user_id: int,
    conversation: AIConversation,
    content: str,
) -> AIConversationMessageOut:
    """发送非流式消息并返回 AI 回复。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前登录用户 ID；必须与 conversation.user_id 一致。
        conversation: AIConversation 实例。
        content: 用户消息内容。

    返回:
        AI 回复消息输出。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    final_state = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=content)],
            "user_id": user_id,
        },
        config,
    )
    messages: list[BaseMessage] = final_state.get("messages", [])
    if not messages:
        raise BusinessError("Failed to get AI response", code=ErrorCode.EXTERNAL_AI_RESPONSE_FAILED)

    await ai_cache_module.invalidate_messages(conversation.id)
    await ai_cache_module.invalidate_conversation_list(conversation.user_id)

    ai_message = messages[-1]
    if not isinstance(ai_message, AIMessage):
        raise BusinessError("Failed to get AI response", code=ErrorCode.EXTERNAL_AI_RESPONSE_FAILED)
    return AIConversationMessageOut(**_message_to_dict(ai_message))


async def stream_message(
    db: AsyncSession,
    *,
    user_id: int,
    conversation: AIConversation,
    content: str,
) -> AsyncIterator[AIStreamChunkOut]:
    """发送消息并以 SSE 流式返回 AI 回复内容。

    流式输出结束后，LangGraph 会自动将完整状态写入 checkpoint。
    本函数同时负责失效相关缓存。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前登录用户 ID；必须与 conversation.user_id 一致。
        conversation: AIConversation 实例。
        content: 用户消息内容。

    返回:
        异步迭代器，产出 AIStreamChunkOut 数据包。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)

    model_name: str | None = None

    async for chunk in graph.astream(
        {
            "messages": [HumanMessage(content=content)],
            "user_id": user_id,
        },
        config,
        stream_mode="messages",
    ):
        message_chunk, metadata = chunk
        if model_name is None:
            model_name = metadata.get("model") if isinstance(metadata, dict) else None

        if isinstance(message_chunk, AIMessageChunk):
            reasoning = message_chunk.additional_kwargs.get("reasoning_content")
            if reasoning:
                yield AIStreamChunkOut(type="reasoning", data=reasoning, model=model_name)
            if message_chunk.content:
                yield AIStreamChunkOut(
                    type="content",
                    data=message_chunk.content,
                    model=model_name,
                )

    await ai_cache_module.invalidate_messages(conversation.id)
    await ai_cache_module.invalidate_conversation_list(conversation.user_id)
    yield AIStreamChunkOut(type="done", data="", model=model_name)


async def delete_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    conversation: AIConversation,
) -> None:
    """软删除 AI 会话。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前登录用户 ID；必须与 conversation.user_id 一致。
        conversation: AIConversation 实例。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    conversation.status = AIConversationStatus.DELETED
    await db.commit()
    await ai_cache_module.invalidate_conversation_list(conversation.user_id)
    await ai_cache_module.invalidate_messages(conversation.id)
