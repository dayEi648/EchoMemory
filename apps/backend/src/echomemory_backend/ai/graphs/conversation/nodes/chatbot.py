"""AI 对话 chatbot 节点。"""

from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.langchain.deepseek_chat import DeepSeekChatModel


def build_chatbot_node(llm: DeepSeekChatModel):
    """构造 chatbot 节点函数。

    返回的节点函数接收当前状态，调用 LLM 生成回复，并将回复追加到消息列表。

    参数:
        llm: 已配置的 DeepSeekChatModel 实例。

    返回:
        chatbot 节点函数。
    """

    async def chatbot_node(state: AIConversationState) -> AIConversationState:
        """调用 LLM 生成 AI 回复并追加到消息列表。"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    return chatbot_node
