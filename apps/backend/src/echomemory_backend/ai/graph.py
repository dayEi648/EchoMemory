"""AI 对话 LangGraph 状态图定义。

定义对话状态、chatbot 节点与边，使用 AsyncPostgresSaver 持久化消息状态。
"""

from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from echomemory_backend.ai.checkpointer import get_checkpointer
from echomemory_backend.ai.llm import DeepSeekChatModel
from echomemory_backend.core.config import settings


class AIConversationState(TypedDict):
    """AI 对话图状态。

    ``messages`` 使用 ``add_messages`` reducer，支持增量追加与 LangGraph 消息类型。
    ``metadata`` 预留用于后续工具结果、用户画像等附加信息。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    metadata: Annotated[dict[str, Any], lambda x, y: {**x, **y}]


def build_graph(model: str | None = None) -> StateGraph:
    """构建并编译 AI 对话状态图。

    参数:
        model: 使用的模型 ID；None 时使用配置默认模型。

    返回:
        编译后的 StateGraph 实例，已绑定 Postgres Checkpointer。
    """
    model_id = model or settings.ai_default_model
    llm = DeepSeekChatModel(model=model_id)

    async def chatbot_node(state: AIConversationState) -> AIConversationState:
        """调用 LLM 生成 AI 回复并追加到消息列表。"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    graph_builder = StateGraph(AIConversationState)
    graph_builder.add_node("chatbot", chatbot_node)
    graph_builder.add_edge(START, "chatbot")
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
