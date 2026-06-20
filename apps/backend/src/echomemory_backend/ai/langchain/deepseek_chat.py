"""LangChain 兼容的 DeepSeek ChatModel 封装。

将 ``ai.clients.deepseek.DeepSeekClient`` 包装为 LangChain ``BaseChatModel``，
使 LangGraph 能够原生使用 DeepSeek 进行异步调用与流式输出。
"""

from __future__ import annotations

import json
import logging
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
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from echomemory_backend.ai.clients.deepseek import ChatMessage, DeepSeekClient
from echomemory_backend.core.config import settings

logger = logging.getLogger(__name__)


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
        return ChatMessage(
            role="assistant",
            content=str(message.content),
            tool_calls=_convert_langchain_tool_calls(message.tool_calls),
        )
    if isinstance(message, ToolMessage):
        return ChatMessage(
            role="tool",
            content=str(message.content),
            tool_call_id=message.tool_call_id,
            name=getattr(message, "name", None),
        )
    raise ValueError(f"不支持发送给 LLM 的消息类型: {type(message).__name__}")


def _convert_langchain_tool_calls(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    """把 LangChain ToolCall 转换为 OpenAI assistant tool_calls。"""
    if not tool_calls:
        return None

    return [
        {
            "id": tool_call.get("id", ""),
            "type": "function",
            "function": {
                "name": tool_call.get("name", ""),
                "arguments": json.dumps(
                    tool_call.get("args", {}),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        }
        for tool_call in tool_calls
    ]


def _filter_llm_messages(messages: list[BaseMessage]) -> list[ChatMessage]:
    """过滤并截断可发送给 LLM 的消息。

    - 保留 SystemMessage、HumanMessage、AIMessage 与 ToolMessage；
      ToolMessage 会透传给模型以支持函数调用上下文。
    - 保留 SystemMessage 与最近的 ``ai_max_context_messages`` 条非系统消息，
      避免上下文窗口无限增长。

    参数:
        messages: 状态中的完整消息列表。

    返回:
        可发送给 LLM 的 ChatMessage 列表。
    """
    system_message: SystemMessage | None = None
    llm_messages: list[BaseMessage] = []
    has_user_message = False

    for message in messages:
        if isinstance(message, SystemMessage):
            if system_message is None:
                system_message = message
            continue
        if isinstance(message, HumanMessage):
            has_user_message = True
        elif isinstance(message, AIMessage) and not has_user_message:
            continue
        try:
            _convert_message(message)
            llm_messages.append(message)
        except ValueError:
            continue

    max_context = settings.ai_max_context_messages
    if len(llm_messages) > max_context:
        start_index = len(llm_messages) - max_context
        while (
            start_index > 0
            and isinstance(llm_messages[start_index], ToolMessage)
        ):
            start_index -= 1
            if (
                isinstance(llm_messages[start_index], AIMessage)
                and llm_messages[start_index].tool_calls
            ):
                break
        llm_messages = llm_messages[start_index:]

    result: list[ChatMessage] = []
    if system_message is not None:
        result.append(_convert_message(system_message))
    result.extend(_convert_message(m) for m in llm_messages)
    return result


def _parse_tool_call_arguments(arguments: str) -> dict[str, Any]:
    """将工具调用的 JSON 参数字符串解析为字典。"""
    if not arguments:
        return {}
    try:
        return json.loads(arguments)
    except json.JSONDecodeError:
        logger.warning("Failed to parse tool call arguments: %s", arguments)
        return {}


def _convert_client_tool_calls(tool_calls: list[dict] | None) -> list[dict[str, Any]]:
    """将 DeepSeekClient 返回的 OpenAI 格式 tool_calls 转为 LangChain ToolCall 列表。"""
    if not tool_calls:
        return []
    result: list[dict[str, Any]] = []
    for tc in tool_calls:
        function = tc.get("function", {})
        result.append(
            {
                "id": tc.get("id", ""),
                "type": "tool_call",
                "name": function.get("name", ""),
                "args": _parse_tool_call_arguments(function.get("arguments", "")),
            }
        )
    return result


def _convert_client_tool_call_chunks(
    tool_call_chunks: list[dict] | None,
) -> list[dict[str, Any]]:
    """把底层流式工具调用片段转换为 LangChain ToolCallChunk。"""
    if not tool_call_chunks:
        return []

    return [
        {
            "name": chunk.get("name"),
            "args": chunk.get("args", ""),
            "id": chunk.get("id"),
            "index": chunk.get("index"),
            "type": "tool_call_chunk",
        }
        for chunk in tool_call_chunks
    ]


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
    enable_thinking: bool = Field(
        default_factory=lambda: settings.deepseek_thinking_type == "enabled"
    )
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

    def bind_tools(
        self,
        tools: Any,
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """绑定工具到模型。

        参数:
            tools: BaseTool 列表或已格式化的工具定义。
            tool_choice: 工具选择策略，如 "auto" / "required" / "none"。

        返回:
            绑定工具后的 Runnable。
        """
        formatted_tools = [convert_to_openai_tool(tool) for tool in tools]
        return self.bind(tools=formatted_tools, tool_choice=tool_choice, **kwargs)

    def _build_chat_messages(self, messages: list[BaseMessage]) -> list[ChatMessage]:
        """构建发送给 DeepSeek 的消息列表。

        参数:
            messages: LangChain 消息列表。

        返回:
            DeepSeek ChatMessage 列表。
        """
        return _filter_llm_messages(messages)

    def _build_ai_message(
        self,
        content: str,
        reasoning_content: str | None = None,
        tool_calls: list[dict] | None = None,
    ) -> AIMessage:
        """根据模型返回构造 AIMessage。

        参数:
            content: 模型生成的文本内容。
            reasoning_content: 思考模型的推理内容，可选。
            tool_calls: 模型请求调用的工具列表，可选。

        返回:
            AIMessage 实例。
        """
        additional_kwargs: dict[str, Any] = {}
        if reasoning_content:
            additional_kwargs["reasoning_content"] = reasoning_content
        return AIMessage(
            content=content,
            tool_calls=_convert_client_tool_calls(tool_calls),
            additional_kwargs=additional_kwargs,
        )

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
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        response = self.client.chat_sync(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        generation = ChatGeneration(
            message=self._build_ai_message(
                response.content,
                response.reasoning_content,
                response.tool_calls,
            )
        )
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
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        response = await self.client.chat(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        generation = ChatGeneration(
            message=self._build_ai_message(
                response.content,
                response.reasoning_content,
                response.tool_calls,
            )
        )
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
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        async for chunk in self.client.chat_stream(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        ):
            additional_kwargs: dict[str, Any] = {}
            if chunk.reasoning_content:
                additional_kwargs["reasoning_content"] = chunk.reasoning_content
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=chunk.content,
                    tool_call_chunks=(
                        _convert_client_tool_call_chunks(chunk.tool_call_chunks)
                        or [
                            {
                                "name": tool_call["name"],
                                "args": json.dumps(
                                    tool_call["args"],
                                    ensure_ascii=False,
                                ),
                                "id": tool_call["id"],
                                "index": index,
                                "type": "tool_call_chunk",
                            }
                            for index, tool_call in enumerate(
                                _convert_client_tool_calls(chunk.tool_calls)
                            )
                        ]
                    ),
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
        tools = kwargs.get("tools")
        tool_choice = kwargs.get("tool_choice")
        for chunk in self.client.chat_stream_sync(
            chat_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        ):
            additional_kwargs: dict[str, Any] = {}
            if chunk.reasoning_content:
                additional_kwargs["reasoning_content"] = chunk.reasoning_content
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=chunk.content,
                    tool_call_chunks=(
                        _convert_client_tool_call_chunks(chunk.tool_call_chunks)
                        or [
                            {
                                "name": tool_call["name"],
                                "args": json.dumps(
                                    tool_call["args"],
                                    ensure_ascii=False,
                                ),
                                "id": tool_call["id"],
                                "index": index,
                                "type": "tool_call_chunk",
                            }
                            for index, tool_call in enumerate(
                                _convert_client_tool_calls(chunk.tool_calls)
                            )
                        ]
                    ),
                    additional_kwargs=additional_kwargs,
                ),
                generation_info={"model": chunk.model} if chunk.model else None,
            )
