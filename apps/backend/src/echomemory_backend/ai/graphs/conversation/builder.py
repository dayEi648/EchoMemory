"""AI 对话工作流状态图构建器。"""

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from echomemory_backend.ai.graphs.checkpointer import get_checkpointer
from echomemory_backend.ai.graphs.conversation.nodes import build_chatbot_node
from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel
from echomemory_backend.core.config import settings


def _route_after_start(state: AIConversationState) -> str:
    """仅在最新消息来自用户时进入 chatbot。

    会话创建阶段只写入系统消息，此时直接结束图执行，避免产生没有用户输入的
    助手消息。正常发送消息时，最新消息为 HumanMessage，进入 chatbot。
    """
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], HumanMessage):
        return "chatbot"
    return END


def build_graph(model: str | None = None) -> CompiledStateGraph:
    """构建并编译 AI 对话状态图。

    参数:
        model: 使用的模型 ID；None 时使用配置默认模型。

    返回:
        编译后的 CompiledStateGraph 实例，已绑定 Postgres Checkpointer。
    """
    model_id = model or settings.ai_default_model
    llm = DeepSeekChatModel(model=model_id)

    chatbot_node = build_chatbot_node(llm)

    graph_builder = StateGraph(AIConversationState)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_conditional_edges(START, _route_after_start)
    graph_builder.add_edge("chatbot", END)

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
