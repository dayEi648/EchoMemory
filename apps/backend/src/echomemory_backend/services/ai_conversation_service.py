"""AI 对话业务服务模块。

提供会话创建、消息发送、消息列表查询、软删除等能力，
直接读写 PostgreSQL 与 LangGraph checkpoint。
"""

from __future__ import annotations
from echomemory_backend.core.exceptions.codes import ErrorCode

import logging
import asyncio
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

from echomemory_backend.ai.clients.deepseek import ChatMessage, DeepSeekClient
from echomemory_backend.ai.graphs.conversation.builder import build_graph
from echomemory_backend.ai.graphs.conversation.nodes.streaming_parser import (
    parse_legacy_tagged_response,
)
from echomemory_backend.ai.graphs.conversation.prompts import (
    get_system_prompt,
    get_title_generation_prompt,
)
from echomemory_backend.ai.monitoring.callbacks import (
    AgentMonitorCallbackHandler,
)
from echomemory_backend.ai.monitoring.context import AgentMonitorSession
from echomemory_backend.ai.monitoring.runtime import (
    bind_monitor,
    get_current_monitor,
)
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.models.ai_conversation import (
    AIConversation,
    AIConversationStatus,
)
from echomemory_backend.models.enums import UserStatus
from echomemory_backend.schemas.ai_conversation import (
    AIConversationMessageRole,
    AIConversationMessageOut,
    AIConversationOut,
    AIStreamChunkOut,
)
from echomemory_backend.services import user_profile_service

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
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            data["tool_calls"] = list(tool_calls)
    elif isinstance(message, ToolMessage):
        data["tool_call_id"] = message.tool_call_id
        data["name"] = message.name
        artifact = getattr(message, "artifact", None)
        if isinstance(artifact, dict):
            data["artifact"] = artifact
    return data


def _messages_to_dicts(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """批量转换 LangChain 消息为 API 输出字典。

    参数:
        messages: LangChain BaseMessage 列表。

    返回:
        输出字典列表。
    """
    return [_message_to_dict(m) for m in messages]


def _filter_messages_for_view(
    messages: list[BaseMessage],
    *,
    message_types: set[AIConversationMessageRole],
    include_intermediate_ai: bool,
) -> list[BaseMessage]:
    """按消息历史视图过滤 checkpoint 中的内部消息。

    参数:
        messages: LangGraph checkpoint 中的完整消息序列。
        message_types: 当前视图允许返回的消息类型。
        include_intermediate_ai: 是否返回带 tool_calls 的中间 AI 消息。

    返回:
        仅包含当前调用者可见消息的列表。
    """
    filtered: list[BaseMessage] = []
    for message in messages:
        if message.type not in message_types:
            continue
        if (
            message.type == "ai"
            and getattr(message, "tool_calls", None)
            and not include_intermediate_ai
        ):
            continue
        filtered.append(message)
    return filtered


_PUBLIC_ATTACHMENT_TYPES = {
    "music_card",
    "playlist_card",
    "album_card",
    "confirmation_card",
}


def _public_tool_artifact(message: BaseMessage) -> dict[str, Any] | None:
    """读取允许投影给当前会话用户的结构化工具附件。"""
    if not isinstance(message, ToolMessage):
        return None
    artifact = getattr(message, "artifact", None)
    if not isinstance(artifact, dict):
        return None
    if artifact.get("type") not in _PUBLIC_ATTACHMENT_TYPES:
        return None
    if artifact.get("version") != 1:
        return None
    return artifact


def _project_messages_for_view(
    messages: list[BaseMessage],
    *,
    message_types: set[AIConversationMessageRole],
    include_intermediate_ai: bool,
) -> list[dict[str, Any]]:
    """把 checkpoint 消息投影为 API 视图，并将工具附件绑定到最终 AI 回复。

    ToolMessage 在普通用户视图中仍保持隐藏，但其中允许公开的 artifact 会附加到
    紧随其后的最终 AI 消息，从而支持历史会话恢复卡片。
    """
    projected: list[dict[str, Any]] = []
    pending_attachments: list[dict[str, Any]] = []

    for message in messages:
        artifact = _public_tool_artifact(message)
        if artifact is not None:
            pending_attachments.append(artifact)

        if message.type not in message_types:
            continue
        if (
            message.type == "ai"
            and getattr(message, "tool_calls", None)
            and not include_intermediate_ai
        ):
            continue

        item = _message_to_dict(message)
        if message.type == "ai" and not getattr(message, "tool_calls", None):
            if pending_attachments:
                item["attachments"] = list(pending_attachments)
                pending_attachments.clear()
        projected.append(item)

    return projected


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


def _is_default_title(title: str) -> bool:
    """判断标题是否为默认占位标题。"""
    return title == settings.ai_default_title


def _sanitize_title(title: str) -> str:
    """清理模型生成的标题。

    去除首尾空白、引号，超长截断，空标题返回默认标题。
    """
    cleaned = title.strip().strip('"').strip("'").strip()
    if not cleaned:
        return settings.ai_default_title
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned


def _is_read_only_user(status: int | None) -> bool:
    """根据用户状态判断是否只允许使用只读工具。"""
    if status is None:
        return False
    return status in (UserStatus.MUTED, UserStatus.RESTRICTED)


def _build_graph_state(
    user_id: int,
    *,
    read_only: bool = False,
    confirmation_token: str | None = None,
) -> dict[str, Any]:
    """构造传入 LangGraph 的 state 基础字段。"""
    return {
        "user_id": user_id,
        "read_only": read_only,
        "confirmation_token": confirmation_token,
    }


def _build_thread_config(
    thread_id: str,
    monitor: AgentMonitorSession | None = None,
) -> dict[str, Any]:
    """构造 LangGraph 线程配置，包含 recursion_limit 等运行时限制。"""
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": settings.ai_tool_recursion_limit,
    }
    if monitor is not None:
        config["callbacks"] = [AgentMonitorCallbackHandler(monitor)]
        config["metadata"] = {
            "agent_monitor_run_id": str(monitor.run_id),
            "agent_scenario": monitor.scenario,
        }
    return config


def _create_conversation_monitor(
    *,
    user_id: int,
    actor_username: str | None,
    conversation: AIConversation,
    operation: str,
    content: str | None,
    confirmation_token: str | None = None,
) -> AgentMonitorSession:
    """创建并启动一条 AI 对话监控运行。"""
    monitor = AgentMonitorSession(
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
        workflow_version="1",
        actor_user_id=user_id,
        actor_username=actor_username,
        subject_type="ai_conversation",
        subject_id=str(conversation.id),
        thread_id=conversation.thread_id,
        model=conversation.model,
        metadata={"operation": operation},
    )
    monitor.start(
        input_value={
            "operation": operation,
            "conversation_id": conversation.id,
            "content": content,
            "confirmation_token": confirmation_token,
        }
    )
    return monitor


async def _get_checkpoint_summary(
    graph: Any,
    config: dict[str, Any],
) -> dict[str, Any]:
    """读取适合监控展示的短期记忆摘要。"""
    try:
        state = await graph.aget_state(config)
    except Exception as exc:
        logger.warning(
            "Failed to read checkpoint summary for Agent monitoring: %s",
            exc,
        )
        return {
            "available": False,
            "error_type": type(exc).__name__,
        }
    values = state.values if state is not None else {}
    messages = list(values.get("messages", []))
    role_counts: dict[str, int] = {}
    for message in messages:
        role_counts[message.type] = role_counts.get(message.type, 0) + 1
    return {
        "message_count": len(messages),
        "role_counts": role_counts,
        "state_keys": sorted(values.keys()),
        "next_nodes": list(state.next) if state is not None else [],
    }


async def generate_conversation_title(
    user_message: str,
    ai_response: str,
    model: str = "deepseek-v4-flash",
) -> str:
    """根据首条用户消息与 AI 回复生成会话标题。

    使用轻量模型（默认 deepseek-v4-flash）进行一次性非流式调用。

    参数:
        user_message: 首条用户消息。
        ai_response: 对应 AI 回复文本。
        model: 用于生成标题的模型 ID。

    返回:
        清理后的标题文本；生成失败时返回默认标题。
    """
    monitor = get_current_monitor()
    prompt = get_title_generation_prompt(user_message, ai_response)
    if monitor is not None:
        monitor.record_event(
            event_type="prompt.rendered",
            component_type="prompt",
            component_name="conversation_title",
            status="SUCCEEDED",
            payload={"prompt": prompt},
        )
    try:
        client = DeepSeekClient(model=model, enable_thinking=False)
        if monitor is not None:
            monitor.record_event(
                event_type="llm.started",
                component_type="llm",
                component_name="conversation_title",
                status="RUNNING",
                payload={"model": model},
            )
        response = await client.chat(
            [ChatMessage(role="system", content=prompt)],
            temperature=0.5,
        )
        if monitor is not None:
            monitor.add_usage(response.usage)
            monitor.record_event(
                event_type="llm.completed",
                component_type="llm",
                component_name="conversation_title",
                status="SUCCEEDED",
                payload={
                    "model": response.model or model,
                    "content": response.content,
                    "usage": response.usage,
                },
            )
        return _sanitize_title(response.content or "")
    except Exception as exc:
        if monitor is not None:
            monitor.record_event(
                event_type="llm.failed",
                component_type="llm",
                component_name="conversation_title",
                status="FAILED",
                error={"type": type(exc).__name__, "message": str(exc)},
            )
        logger.exception("Failed to generate conversation title")
        return settings.ai_default_title


async def update_conversation_title(
    db: AsyncSession,
    *,
    user_id: int,
    conversation: AIConversation,
    title: str,
) -> AIConversation:
    """手动更新会话标题。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前登录用户 ID；必须与 conversation.user_id 一致。
        conversation: AIConversation 实例。
        title: 新标题。

    返回:
        更新后的 AIConversation 实例。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError(
            "Permission denied", code=ErrorCode.AI_CONVERSATION_PERMISSION_DENIED
        )

    conversation.title = _sanitize_title(title)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def create_conversation(
    db: AsyncSession,
    *,
    user_id: int,
    actor_username: str | None = None,
    title: str | None = None,
    model: str | None = None,
    first_message: str | None = None,
    read_only: bool = False,
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
        read_only: 是否只允许使用只读工具。

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
    monitor = _create_conversation_monitor(
        user_id=user_id,
        actor_username=actor_username,
        conversation=conversation,
        operation="create",
        content=first_message,
    )

    graph = build_graph(conversation.model)
    config = _build_thread_config(conversation.thread_id, monitor)
    system_prompt = get_system_prompt()
    monitor.record_event(
        event_type="prompt.initialized",
        component_type="prompt",
        component_name="conversation_system",
        status="SUCCEEDED",
        payload={"prompt": system_prompt},
    )
    try:
        with bind_monitor(monitor):
            await graph.ainvoke(
                {
                    "messages": [SystemMessage(content=system_prompt)],
                    **_build_graph_state(user_id, read_only=read_only),
                },
                config,
            )
        monitor.record_event(
            event_type="memory.short_term.initialized",
            component_type="memory",
            component_name="langgraph_checkpoint",
            status="SUCCEEDED",
            payload=await _get_checkpoint_summary(graph, config),
        )
    except Exception as exc:
        monitor.fail(exc)
        await db.rollback()
        raise

    await db.commit()
    await db.refresh(conversation)

    ai_reply: AIConversationMessageOut | None = None
    if first_message:
        ai_reply = await send_message(
            db,
            user_id=user_id,
            actor_username=actor_username,
            conversation=conversation,
            content=first_message,
            read_only=read_only,
            monitor=monitor,
        )
    else:
        monitor.complete(
            output_value={
                "conversation_id": conversation.id,
                "initialized": True,
            }
        )

    return conversation, ai_reply


async def stream_first_message(
    db: AsyncSession,
    *,
    user_id: int,
    actor_username: str | None = None,
    title: str | None = None,
    model: str | None = None,
    content: str,
    read_only: bool = False,
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
        read_only: 是否只允许使用只读工具。

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
    monitor = _create_conversation_monitor(
        user_id=user_id,
        actor_username=actor_username,
        conversation=conversation,
        operation="create_stream",
        content=content,
    )

    graph = build_graph(conversation.model)
    config = _build_thread_config(conversation.thread_id, monitor)
    system_prompt = get_system_prompt()
    monitor.record_event(
        event_type="prompt.initialized",
        component_type="prompt",
        component_name="conversation_system",
        status="SUCCEEDED",
        payload={"prompt": system_prompt},
    )
    try:
        with bind_monitor(monitor):
            await graph.ainvoke(
                {
                    "messages": [SystemMessage(content=system_prompt)],
                    **_build_graph_state(user_id, read_only=read_only),
                },
                config,
            )
        monitor.record_event(
            event_type="memory.short_term.initialized",
            component_type="memory",
            component_name="langgraph_checkpoint",
            status="SUCCEEDED",
            payload=await _get_checkpoint_summary(graph, config),
        )
    except Exception as exc:
        monitor.fail(exc)
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
        db,
        user_id=user_id,
        actor_username=actor_username,
        conversation=conversation,
        content=content,
        read_only=read_only,
        monitor=monitor,
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
        raise BusinessError(
            "Conversation not found", code=ErrorCode.AI_CONVERSATION_NOT_FOUND
        )
    if conversation.status == AIConversationStatus.DELETED:
        raise BusinessError(
            "Conversation not found", code=ErrorCode.AI_CONVERSATION_NOT_FOUND
        )
    return conversation


async def get_messages(
    db: AsyncSession,
    *,
    conversation: AIConversation,
    message_types: set[AIConversationMessageRole],
    include_intermediate_ai: bool = False,
) -> list[AIConversationMessageOut]:
    """获取会话消息列表。

    直接从 LangGraph checkpoint 加载状态。

    参数:
        db: SQLAlchemy 异步 Session（兼容性参数，实际读取 checkpoint）。
        conversation: AIConversation 实例。
        message_types: 需要返回的消息类型。
        include_intermediate_ai: 是否包含发起工具调用的中间 AI 消息。

    返回:
        AIConversationMessageOut 列表。
    """
    graph = build_graph(conversation.model)
    config = _build_thread_config(conversation.thread_id)
    state = await graph.aget_state(config)
    messages = state.values.get("messages", []) if state else []
    messages = _remove_orphan_assistant_messages(messages)
    projected = _project_messages_for_view(
        messages,
        message_types=message_types,
        include_intermediate_ai=include_intermediate_ai,
    )
    return [AIConversationMessageOut(**item) for item in projected]


async def send_message(
    db: AsyncSession,
    *,
    user_id: int,
    actor_username: str | None = None,
    conversation: AIConversation,
    content: str,
    read_only: bool = False,
    confirmation_token: str | None = None,
    monitor: AgentMonitorSession | None = None,
) -> AIConversationMessageOut:
    """发送非流式消息并返回 AI 回复。

    参数:
        db: SQLAlchemy 异步 Session。
        user_id: 当前登录用户 ID；必须与 conversation.user_id 一致。
        conversation: AIConversation 实例。
        content: 用户消息内容。
        read_only: 是否只允许使用只读工具。

    返回:
        AI 回复消息输出。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    monitor = monitor or _create_conversation_monitor(
        user_id=user_id,
        actor_username=actor_username,
        conversation=conversation,
        operation="send_message",
        content=content,
        confirmation_token=confirmation_token,
    )
    monitor.record_event(
        event_type="message.received",
        component_type="message",
        component_name="human",
        status="SUCCEEDED",
        payload={"content": content},
    )
    graph = build_graph(conversation.model)
    config = _build_thread_config(conversation.thread_id, monitor)
    before_summary = await _get_checkpoint_summary(graph, config)
    try:
        with bind_monitor(monitor):
            final_state = await graph.ainvoke(
                {
                    "messages": [HumanMessage(content=content)],
                    **_build_graph_state(
                        user_id,
                        read_only=read_only,
                        confirmation_token=confirmation_token,
                    ),
                },
                config,
            )
    except Exception as exc:
        monitor.fail(exc)
        raise

    messages: list[BaseMessage] = final_state.get("messages", [])
    if not messages:
        error = BusinessError(
            "Failed to get AI response", code=ErrorCode.EXTERNAL_AI_RESPONSE_FAILED
        )
        monitor.fail(error)
        raise error

    ai_message = messages[-1]
    if not isinstance(ai_message, AIMessage):
        error = BusinessError(
            "Failed to get AI response", code=ErrorCode.EXTERNAL_AI_RESPONSE_FAILED
        )
        monitor.fail(error)
        raise error

    projected_ai_messages = _project_messages_for_view(
        messages,
        message_types={"ai"},
        include_intermediate_ai=False,
    )
    ai_reply = AIConversationMessageOut(**projected_ai_messages[-1])
    monitor.record_event(
        event_type="memory.short_term.updated",
        component_type="memory",
        component_name="langgraph_checkpoint",
        status="SUCCEEDED",
        payload={
            "before": before_summary,
            "after": await _get_checkpoint_summary(graph, config),
        },
    )

    with bind_monitor(monitor):
        if _is_default_title(conversation.title):
            try:
                title = await generate_conversation_title(
                    content, str(ai_reply.content or "")
                )
                if not _is_default_title(title):
                    conversation.title = title
                    await db.commit()
                    await db.refresh(conversation)
            except Exception:
                logger.exception(
                    "Failed to auto-generate title for conversation %s",
                    conversation.id,
                )

        try:
            await user_profile_service.maybe_update_user_profile(
                db, user_id=user_id, conversation=conversation
            )
        except Exception:
            logger.exception(
                "Failed to update user profile for conversation %s",
                conversation.id,
            )

    monitor.complete(output_value=ai_reply.model_dump(mode="json"))
    return ai_reply


async def stream_message(
    db: AsyncSession,
    *,
    user_id: int,
    actor_username: str | None = None,
    conversation: AIConversation,
    content: str,
    read_only: bool = False,
    confirmation_token: str | None = None,
    monitor: AgentMonitorSession | None = None,
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
        read_only: 是否只允许使用只读工具。

    返回:
        异步迭代器，产出 AIStreamChunkOut 数据包。

    异常:
        BusinessError: user_id 与 conversation 所属用户不一致时抛出 403。
    """
    if user_id != conversation.user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    monitor = monitor or _create_conversation_monitor(
        user_id=user_id,
        actor_username=actor_username,
        conversation=conversation,
        operation="stream_message",
        content=content,
        confirmation_token=confirmation_token,
    )
    monitor.record_event(
        event_type="message.received",
        component_type="message",
        component_name="human",
        status="SUCCEEDED",
        payload={"content": content},
    )
    graph = build_graph(conversation.model)
    config = _build_thread_config(conversation.thread_id, monitor)
    before_summary = await _get_checkpoint_summary(graph, config)

    model_name: str | None = conversation.model
    accumulated_content = ""

    try:
        with bind_monitor(monitor):
            async for message_chunk, metadata in graph.astream(
                {
                    "messages": [HumanMessage(content=content)],
                    **_build_graph_state(
                        user_id,
                        read_only=read_only,
                        confirmation_token=confirmation_token,
                    ),
                },
                config,
                stream_mode="messages",
            ):
                if model_name is None and isinstance(metadata, dict):
                    model_name = metadata.get("model")
                if isinstance(message_chunk, ToolMessage):
                    artifact = _public_tool_artifact(message_chunk)
                    if artifact is not None:
                        yield AIStreamChunkOut(
                            type="attachment",
                            data="",
                            model=model_name,
                            meta={"attachment": artifact},
                        )
                    continue
                if not isinstance(message_chunk, AIMessageChunk):
                    continue

                reasoning = message_chunk.additional_kwargs.get(
                    "reasoning_content"
                )
                if isinstance(reasoning, str) and reasoning:
                    yield AIStreamChunkOut(
                        type="reasoning", data=reasoning, model=model_name
                    )

                if (
                    isinstance(message_chunk.content, str)
                    and message_chunk.content
                ):
                    accumulated_content += message_chunk.content
                    yield AIStreamChunkOut(
                        type="content",
                        data=message_chunk.content,
                        model=model_name,
                    )

            # 标题生成在 done 前完成，确保前端刷新列表时标题已生效。
            if _is_default_title(conversation.title) and accumulated_content:
                try:
                    title = await generate_conversation_title(
                        content, accumulated_content
                    )
                    if not _is_default_title(title):
                        conversation.title = title
                        await db.commit()
                        await db.refresh(conversation)
                except Exception:
                    logger.exception(
                        "Failed to auto-generate title for conversation %s",
                        conversation.id,
                    )

        monitor.record_event(
            event_type="memory.short_term.updated",
            component_type="memory",
            component_name="langgraph_checkpoint",
            status="SUCCEEDED",
            payload={
                "before": before_summary,
                "after": await _get_checkpoint_summary(graph, config),
            },
        )
    except (asyncio.CancelledError, GeneratorExit):
        monitor.cancel("stream consumer disconnected")
        raise
    except Exception as exc:
        monitor.fail(exc)
        logger.exception("AI stream failed for conversation %s", conversation.id)
        yield AIStreamChunkOut(
            type="error",
            data="AI 流式响应失败",
            model=model_name,
        )
        return

    with bind_monitor(monitor):
        try:
            await user_profile_service.maybe_update_user_profile(
                db, user_id=user_id, conversation=conversation
            )
        except Exception:
            logger.exception(
                "Failed to update user profile for conversation %s",
                conversation.id,
            )

    # done 是客户端停止读取的协议边界，必须在画像维护完成后发送。
    monitor.complete(
        output_value={"content": accumulated_content, "model": model_name}
    )
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
