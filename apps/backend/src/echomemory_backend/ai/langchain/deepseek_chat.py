"""LangChain 兼容的 DeepSeek ChatModel 封装。

将 ``ai.clients.deepseek.DeepSeekClient`` 包装为 LangChain ``BaseChatModel``，
使 LangGraph 能够原生使用 DeepSeek 进行异步调用与流式输出。
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from echomemory_backend.ai.clients.deepseek import ChatMessage, DeepSeekClient
from echomemory_backend.core.config import settings


def _convert_message(message: BaseMessage) -> ChatMessage:
    """将 LangChain 消息转换为 DeepSeekClient 可接受的 ChatMessage。

    参数:
        message: LangChain BaseMessage 实例。

    返回:
        ChatMessage 实例。

    异常:
        ValueError: 不支持的消息类型。
    """
    if isinstance(message, SystemMessage):
        return ChatMessage(role="system", content=str(message.content))
    if isinstance(message, HumanMessage):
        return ChatMessage(role="user", content=str(message.content))
    if isinstance(message, AIMessage):
        return ChatMessage(role="assistant", content=str(message.content))
    raise ValueError(f"不支持发送给 LLM 的消息类型: {type(message).__name__}")


def _filter_llm_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
    """过滤并截断可发送给 LLM 的消息。

    - ToolMessage 仅用于状态保存，不透传给模型。
    - 保留 SystemMessage 与最近的 ``ai_max_context_messages`` 条消息，
      避免上下文窗口无限增长。

    参数:
        messages: 状态中的完整消息列表。

    返回:
        可发送给 LLM 的 ChatMessage 列表。
    """
    system_message: SystemMessage | None = None
    llm_messages: list[BaseMessage] = []

    for message in messages:
        if message.type == "tool":
            continue
        if isinstance(message, SystemMessage):
            if system_message is None:
                system_message = message
            continue
        try:
            _convert_message(message)
            llm_messages.append(message)
        except ValueError:
            continue

    max_context = settings.ai_max_context_messages
    if len(llm_messages) > max_context:
        llm_messages = llm_messages[-max_context:]

    result: list[ChatMessage] = []
    if system_message is not None:
        result.append(_convert_message(system_message))
    result.extend(_convert_message(m) for m in llm_messages)
    return result


class DeepSeekChatModel(BaseChatModel):
    """LangChain 兼容的 DeepSeek 对话模型。

    属性:
        model: 模型 ID，如 deepseek-v4-pro / deepseek-v4-flash。
        enable_thinking: 是否启用 reasoning 模式。
        temperature: 采样温度。
        max_tokens: 最大生成 token 数。
        timeout: 请求超时时间。
    """

    model: str = Field(default_factory=lambda: settings.ai_default_model)
    enable_thinking: bool = False
    temperature: float = Field(default_factory=lambda: settings.deepseek_default_temperature)
    max_tokens: int | None = None
    timeout: float = Field(default_factory=lambda: settings.deepseek_default_timeout)

    _client: DeepSeekClient | None = None

    @property
    def _llm_type(self) -> str:
        """返回 LangChain 内部使用的 LLM 类型标识。"""
        return "deepseek-chat"

    @property
    def client(self) -> DeepSeekClient:
        """返回懒加载的 DeepSeekClient 实例。"""
        if self._client is None:
            self._client = DeepSeekClient(
                model=self.model,
                enable_thinking=self.enable_thinking,
                timeout=self.timeout,
            )
        return self._client

    def _build_chat_messages(self, messages: list[BaseMessage]) -> list[ChatMessage]:
        """构建发送给 DeepSeek 的消息列表。

        参数:
            messages: LangChain 消息列表。

        返回:
            DeepSeek ChatMessage 列表。
        """
        return _filter_llm_messages(messages)

    def _build_ai_message(self, content: str, reasoning_content: str | None = None) -> AIMessage:
        """根据模型返回构造 AIMessage。

        参数:
            content: 模型生成的文本内容。
            reasoning_content: 思考模型的推理内容，可选。

        返回:
            AIMessage 实例。
        """
        additional_kwargs: dict[str, Any] = {}
        if reasoning_content:
            additional_kwargs["reasoning_content"] = reasoning_content
        return AIMessage(content=content, additional_kwargs=additional_kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """同步生成模型回复（LangChain 接口要求）。

        异步场景请使用 ``_agenerate`` 或 ``_astream``；
        本方法主要用于兼容 LangChain 同步调用链。
        """
        chat_messages = self._build_chat_messages(messages)
        response = self.client.chat_sync(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        generation = ChatGeneration(message=self._build_ai_message(response.content, response.reasoning_content))
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """异步生成模型回复。"""
        chat_messages = self._build_chat_messages(messages)
        response = await self.client.chat(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        generation = ChatGeneration(message=self._build_ai_message(response.content, response.reasoning_content))
        return ChatResult(generations=[generation])

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """异步流式生成模型回复。"""
        chat_messages = self._build_chat_messages(messages)
        async for chunk in self.client.chat_stream(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ):
            additional_kwargs: dict[str, Any] = {}
            if chunk.reasoning_content:
                additional_kwargs["reasoning_content"] = chunk.reasoning_content
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=chunk.content,
                    additional_kwargs=additional_kwargs,
                ),
                generation_info={"model": chunk.model} if chunk.model else None,
            )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """同步流式生成模型回复（LangChain 接口要求）。"""
        chat_messages = self._build_chat_messages(messages)
        for chunk in self.client.chat_stream_sync(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ):
            additional_kwargs: dict[str, Any] = {}
            if chunk.reasoning_content:
                additional_kwargs["reasoning_content"] = chunk.reasoning_content
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=chunk.content,
                    additional_kwargs=additional_kwargs,
                ),
                generation_info={"model": chunk.model} if chunk.model else None,
            )
