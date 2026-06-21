"""AI 对话工作流状态图构建器。"""

import secrets
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition

from echomemory_backend.ai.graphs.checkpointer import get_checkpointer
from echomemory_backend.ai.graphs.conversation.nodes import (
    build_chatbot_node,
    build_tool_node,
)
from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel
from echomemory_backend.ai.tools import get_tool_registry
from echomemory_backend.core.config import settings


def _route_after_start(state: AIConversationState) -> str:
    """仅在最新消息来自用户时进入 chatbot。

    会话创建阶段只写入系统消息，此时直接结束图执行，避免产生没有用户输入的
    助手消息。正常发送消息时，最新消息为 HumanMessage，进入 chatbot。
    """
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], HumanMessage):
        if state.get("confirmation_token"):
            return "confirmation"
        return "chatbot"
    return END


def _confirmation_node(state: AIConversationState) -> AIConversationState:
    """把前端签名确认确定性转换为收藏执行工具调用。

    二次确认是权限边界，不能依赖模型是否理解隐藏运行时字段。确认凭证仍由工具
    自身完成签名、用户绑定、过期和重放校验。
    """
    return {
        "messages": [
            AIMessage(
                content="",
                additional_kwargs={"reasoning_content": ""},
                tool_calls=[
                    {
                        "name": "confirm_collection_change",
                        "args": {},
                        "id": f"confirm-{secrets.token_urlsafe(12)}",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }


def build_graph(model: str | None = None) -> CompiledStateGraph:
    """构建并编译 AI 对话状态图。

    参数:
        model: 使用的模型 ID；None 时使用配置默认模型。

    返回:
        编译后的 CompiledStateGraph 实例，已绑定 Postgres Checkpointer
        与工具调用循环。
    """
    model_id = model or settings.ai_default_model
    llm = DeepSeekChatModel(model=model_id)
    registry = get_tool_registry()

    chatbot_node = build_chatbot_node(llm, registry)
    tool_node = build_tool_node(registry)

    graph_builder = StateGraph(AIConversationState)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_node("confirmation", _confirmation_node)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_conditional_edges(START, _route_after_start)
    graph_builder.add_edge("confirmation", "tools")
    graph_builder.add_conditional_edges(
        "chatbot",
        tools_condition,
        {"tools": "tools", "__end__": END},
    )
    graph_builder.add_edge("tools", "chatbot")

    checkpointer = get_checkpointer()
    return graph_builder.compile(checkpointer=checkpointer)


def get_thread_config(thread_id: str) -> dict[str, Any]:
    """构造 LangGraph 线程配置。

    参数:
        thread_id: 会话线程标识，通常与 ``AIConversation.thread_id`` 一致。

    返回:
        包含 configurable thread_id 的字典，用于 invoke / aget_state 等接口。
    """
    return {"configurable": {"thread_id": thread_id}}
