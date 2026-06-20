"""AI 对话业务服务模块。

提供会话创建、消息发送、消息列表查询、软删除等能力，
直接读写 PostgreSQL 与 LangGraph checkpoint。
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
from echomemory_backend.ai.graphs.conversation.nodes.streaming_parser import (
    parse_legacy_tagged_response,
)
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
        reasoning = message.additional_kwargs.get("reasoning_content")
        if isinstance(message.content, str) and not reasoning:
            content, reasoning = parse_legacy_tagged_response(message.content)
            data["content"] = content
        data["reasoning_content"] = reasoning
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


def _remove_orphan_assistant_messages(
    messages: list[BaseMessage],
) -> list[BaseMessage]:
    """移除首条用户消息之前的 AI 消息。

    早期会话初始化会误执行 chatbot，并把无用户输入的回复写入 checkpoint。
    该兼容过滤同时避免旧数据继续显示在前端。
    """
    filtered: list[BaseMessage] = []
    has_user_message = False
    for message in messages:
        if isinstance(message, HumanMessage):
            has_user_message = True
        elif isinstance(message, AIMessage) and not has_user_message:
            continue
        filtered.append(message)
    return filtered


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

    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    try:
        await graph.ainvoke(
            {
                "messages": [SystemMessage(content=get_system_prompt())],
                "user_id": user_id,
            },
            config,
        )
    except Exception:
        await db.rollback()
        raise

    await db.commit()
    await db.refresh(conversation)

    ai_reply: AIConversationMessageOut | None = None
    if first_message:
        ai_reply = await send_message(
            db, user_id=user_id, conversation=conversation, content=first_message
        )

    return conversation, ai_reply


async def stream_first_message(
    db: AsyncSession,
    *,
    user_id: int,
    title: str | None = None,
    model: str | None = None,
    content: str,
) -> AsyncIterator[AIStreamChunkOut]:
    """创建会话并流式返回首条 AI 回复。

    先持久化会话元数据与初始系统消息，再对首条用户消息进行流式生成。
    返回的 chunk 序列与普通 stream_message 一致，以 done 结束。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        title: 会话标题；None 时使用默认标题。
        model: 模型 ID；None 时使用配置默认模型。
        content: 首条用户消息内容。

    返回:
        异步迭代器，产出 AIStreamChunkOut 数据包。
    """
    conversation = AIConversation(
        user_id=user_id,
        title=title or settings.ai_default_title,
        model=model or settings.ai_default_model,
        status=AIConversationStatus.ACTIVE,
        thread_id="",
    )
    db.add(conversation)
    await db.flush()
    conversation.thread_id = str(conversation.id)

    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    try:
        await graph.ainvoke(
            {
                "messages": [SystemMessage(content=get_system_prompt())],
                "user_id": user_id,
            },
            config,
        )
    except Exception:
        await db.rollback()
        raise

    await db.commit()
    await db.refresh(conversation)

    # 将会话元数据作为首包返回，方便前端立即切换会话
    conversation_out = AIConversationOut.model_validate(conversation)
    yield AIStreamChunkOut(
        type="content",
        data="",
        model=conversation.model,
        meta={"conversation": conversation_out.model_dump()},
    )

    async for chunk in stream_message(
        db, user_id=user_id, conversation=conversation, content=content
    ):
        yield chunk


async def list_conversations(
    db: AsyncSession,
    *,
    user_id: int,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    """分页列出当前用户的 AI 会话。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限。
        offset: 偏移量。

    返回:
        {"items": AIConversationOut 列表, "total": 总记录数}。
    """
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
        raise BusinessError("Conversation not found", code=ErrorCode.AI_CONVERSATION_NOT_FOUND)
    if conversation.status == AIConversationStatus.DELETED:
        raise BusinessError("Conversation not found", code=ErrorCode.AI_CONVERSATION_NOT_FOUND)
    return conversation


async def get_messages(
    db: AsyncSession,
    *,
    conversation: AIConversation,
) -> list[AIConversationMessageOut]:
    """获取会话消息列表。

    直接从 LangGraph checkpoint 加载状态。

    参数:
        db: SQLAlchemy 异步 Session（兼容性参数，实际读取 checkpoint）。
        conversation: AIConversation 实例。

    返回:
        AIConversationMessageOut 列表。
    """
    graph = build_graph(conversation.model)
    config = get_thread_config(conversation.thread_id)
    state = await graph.aget_state(config)
    messages = state.values.get("messages", []) if state else []
    messages = _remove_orphan_assistant_messages(messages)
    return [AIConversationMessageOut(**msg) for msg in _messages_to_dicts(messages)]


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

    使用 LangGraph messages 流捕获 LLM token 事件，并将 DeepSeek 原生
    ``reasoning_content`` 与最终 ``content`` 分别输出。
    流式输出结束后，LangGraph 会自动将完整状态写入 checkpoint。

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

    model_name: str | None = conversation.model
    emitted_error = False

    try:
        async for message_chunk, metadata in graph.astream(
            {
                "messages": [HumanMessage(content=content)],
                "user_id": user_id,
            },
            config,
            stream_mode="messages",
        ):
            if model_name is None and isinstance(metadata, dict):
                model_name = metadata.get("model")
            if not isinstance(message_chunk, AIMessageChunk):
                continue

            reasoning = message_chunk.additional_kwargs.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                yield AIStreamChunkOut(type="reasoning", data=reasoning, model=model_name)

            if isinstance(message_chunk.content, str) and message_chunk.content:
                yield AIStreamChunkOut(
                    type="content",
                    data=message_chunk.content,
                    model=model_name,
                )

    except Exception:
        logger.exception(
            "AI stream failed for conversation %s", conversation.id
        )
        emitted_error = True
        yield AIStreamChunkOut(
            type="error",
            data="AI 流式响应失败",
            model=model_name,
        )
    finally:
        if not emitted_error:
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
