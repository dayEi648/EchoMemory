"""AI 对话 chatbot 节点。"""

from langchain_core.messages import AIMessageChunk

from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel


def build_chatbot_node(llm: DeepSeekChatModel):
    """构造 chatbot 节点函数。

    节点内部使用流式调用收集完整回复，以便 LangGraph astream_events
    能够产出 token 级事件；节点最终返回完整 AIMessage。

    参数:
        llm: 已配置的 DeepSeekChatModel 实例。

    返回:
        chatbot 节点函数。
    """

    async def chatbot_node(state: AIConversationState) -> AIConversationState:
        """调用 LLM 生成 AI 回复并追加到消息列表。"""
        accumulated: AIMessageChunk | None = None
        async for chunk in llm.astream(state["messages"]):
            if accumulated is None:
                accumulated = chunk
            else:
                accumulated += chunk

        if accumulated is None:
            return {"messages": []}

        return {"messages": [accumulated]}

    return chatbot_node
