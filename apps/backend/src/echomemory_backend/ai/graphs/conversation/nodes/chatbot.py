"""AI 对话 chatbot 节点。"""

from langchain_core.messages import AIMessageChunk

from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel
from echomemory_backend.ai.tools.registry import ToolRegistry, ToolResolutionContext


def build_chatbot_node(llm: DeepSeekChatModel, registry: ToolRegistry):
    """构造 chatbot 节点函数。

    节点内部使用流式调用收集完整回复，以便 LangGraph astream_events
    能够产出 token 级事件；节点最终返回完整 AIMessage。

    每次调用前会根据 ``registry`` 动态解析当前可用的工具并绑定到模型。

    参数:
        llm: 已配置的 DeepSeekChatModel 实例。
        registry: 工具注册中心，用于动态解析可用工具。

    返回:
        chatbot 节点函数。
    """

    async def chatbot_node(state: AIConversationState) -> AIConversationState:
        """调用 LLM 生成 AI 回复并追加到消息列表。"""
        context = ToolResolutionContext(
            user_id=state.get("user_id"),
            read_only=state.get("read_only", False),
        )
        available_tools = registry.resolve_tools(context)

        llm_with_tools = (
            llm.bind_tools(available_tools)
            if available_tools
            else llm
        )

        accumulated: AIMessageChunk | None = None
        async for chunk in llm_with_tools.astream(state["messages"]):
            if accumulated is None:
                accumulated = chunk
            else:
                accumulated += chunk

        if accumulated is None:
            return {"messages": []}

        return {"messages": [accumulated]}

    return chatbot_node
