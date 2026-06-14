"""DeepSeek LLM 客户端封装。

提供 deepseek-v4-pro（思考模型）与 deepseek-v4-flash（快速模型）两种调用入口，
基于 OpenAI 兼容接口访问 DeepSeek 官方 API，支持异步与同步调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import AsyncIterator, Iterator, Literal

from openai import AsyncOpenAI, OpenAI

from echomemory_backend.core.config import settings


# 可调用的默认参数，优先从 config.py / 环境变量读取，便于集中维护。
DEFAULT_TEMPERATURE: float = settings.deepseek_default_temperature
DEFAULT_TIMEOUT: float = settings.deepseek_default_timeout
REASONING_EFFORT: str = settings.deepseek_reasoning_effort
THINKING_TYPE: str = settings.deepseek_thinking_type

# DeepSeek V4 系列官方上下文窗口长度（来源：官方定价页）。
# 该值为模型固定规格，API 不会返回；需要用于计算上下文占用百分比。
MODEL_CONTEXT_WINDOWS: MappingProxyType[str, int] = MappingProxyType({
    "deepseek-v4-pro": 1_000_000,
    "deepseek-v4-flash": 1_000_000,
})
DEFAULT_CONTEXT_WINDOW: int = 1_000_000


def get_context_window(model_id: str) -> int:
    """返回指定模型 ID 的官方上下文窗口长度。

    参数:
        model_id: DeepSeek 模型 ID。

    返回:
        上下文窗口 token 数；未知模型返回默认值。
    """
    return MODEL_CONTEXT_WINDOWS.get(model_id, DEFAULT_CONTEXT_WINDOW)


def calculate_context_usage_percentage(
    usage: dict,
    model_id: str,
) -> float:
    """根据 usage 统计精确计算上下文窗口占用百分比。

    上下文占用应使用 API 返回的 ``prompt_tokens``（输入侧累计 token 数）
    除以模型官方上下文窗口长度，而非 ``total_tokens``。

    参数:
        usage: DeepSeek 返回的 usage 字典，需包含 prompt_tokens。
        model_id: DeepSeek 模型 ID，用于确定上下文窗口上限。

    返回:
        已用上下文百分比，范围 0~100；usage 无效时返回 0.0。
    """
    if not usage:
        return 0.0
    prompt_tokens = usage.get("prompt_tokens")
    if not isinstance(prompt_tokens, int) or prompt_tokens <= 0:
        return 0.0
    context_window = get_context_window(model_id)
    return round((prompt_tokens / context_window) * 100, 4)


@dataclass(frozen=True)
class ChatMessage:
    """单条聊天消息。

    属性:
        role: 消息角色，仅支持 system、user、assistant。
        content: 消息文本内容。
    """

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class ChatResponse:
    """模型返回的聊天结果。

    属性:
        content: 模型生成的最终文本。
        reasoning_content: 思考模型产生的推理过程文本；非思考模型为 None。
        model: 实际响应使用的模型名称。
        usage: token 使用统计字典。
    """

    content: str
    reasoning_content: str | None = None
    model: str | None = None
    usage: dict | None = None


class DeepSeekClient:
    """DeepSeek API 专属客户端。

    使用 OpenAI 兼容协议访问 DeepSeek，支持异步与同步调用，以及流式输出。
    当 ``enable_thinking=True`` 时，请求会显式启用 thinking 模式，
    推理内容通过 ``ChatResponse.reasoning_content`` 暴露。

    内部对 ``AsyncOpenAI`` / ``OpenAI`` 采用懒加载：仅在首次调用时才构造实际客户端，
    避免应用启动或服务导入时因未配置 API key 而失败。
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        enable_thinking: bool = False,
    ) -> None:
        """初始化 DeepSeek 客户端。

        参数:
            model: 使用的模型 ID，例如 deepseek-v4-pro 或 deepseek-v4-flash。
            api_key: DeepSeek API 密钥；默认使用 settings.deepseek_api_key。
            base_url: DeepSeek API 基础地址；默认使用 settings.deepseek_base_url。
            timeout: 单次请求超时时间（秒）。
            enable_thinking: 是否启用 thinking / reasoning 模式。

        异常:
            ValueError: 当 model 为空字符串时抛出。
        """
        if not model:
            raise ValueError("model 不能为空")

        self.model = model
        self._enable_thinking = enable_thinking
        self._api_key = api_key if api_key is not None else settings.deepseek_api_key
        self._base_url = base_url if base_url is not None else settings.deepseek_base_url
        self._timeout = timeout
        self._async_client: AsyncOpenAI | None = None
        self._sync_client: OpenAI | None = None

    @property
    def _openai_client(self) -> AsyncOpenAI:
        """返回懒加载的 AsyncOpenAI 客户端实例。"""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._async_client

    @property
    def _openai_sync_client(self) -> OpenAI:
        """返回懒加载的同步 OpenAI 客户端实例。"""
        if self._sync_client is None:
            self._sync_client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._sync_client

    def _build_request(
        self,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        stream: bool,
    ) -> dict:
        """构造发送给 DeepSeek API 的请求体。

        参数:
            messages: 对话上下文消息列表。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数，None 表示由服务端决定。
            stream: 是否使用流式输出。

        返回:
            可直接传给 ``AsyncOpenAI.chat.completions.create`` 的字典参数。
        """
        body: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream_options"] = {"include_usage": True}
        if self._enable_thinking:
            body["reasoning_effort"] = REASONING_EFFORT
            body["extra_body"] = {"thinking": {"type": THINKING_TYPE}}
        return body

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """发送非流式聊天请求并返回模型回复。

        参数:
            messages: 对话上下文消息列表。
            temperature: 采样温度，建议范围 0~2。
            max_tokens: 最大生成 token 数，None 表示由服务端决定。

        返回:
            包含回复正文、推理内容（如有）与使用统计的 ChatResponse。

        异常:
            openai.APIError: DeepSeek API 返回错误时抛出。
        """
        body = self._build_request(messages, temperature, max_tokens, stream=False)
        response = await self._openai_client.chat.completions.create(**body)
        message = response.choices[0].message
        return ChatResponse(
            content=message.content or "",
            reasoning_content=getattr(message, "reasoning_content", None),
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None,
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatResponse]:
        """发送流式聊天请求，逐块返回增量内容。

        参数:
            messages: 对话上下文消息列表。
            temperature: 采样温度，建议范围 0~2。
            max_tokens: 最大生成 token 数，None 表示由服务端决定。

        返回:
            异步迭代器，每次产出当前增量文本的 ChatResponse。

        异常:
            openai.APIError: DeepSeek API 返回错误时抛出。
        """
        body = self._build_request(messages, temperature, max_tokens, stream=True)
        stream = await self._openai_client.chat.completions.create(**body)
        async for chunk in stream:
            # DeepSeek 在启用 stream_options.include_usage 后，会在 [DONE] 之前
            # 额外发送一个 choices 为空、usage 为总统计的 chunk。
            if chunk.usage is not None:
                yield ChatResponse(
                    content="",
                    reasoning_content=None,
                    model=chunk.model,
                    usage=chunk.usage.model_dump(),
                )
                continue
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            yield ChatResponse(
                content=delta.content or "",
                reasoning_content=getattr(delta, "reasoning_content", None),
                model=chunk.model,
                usage=None,
            )

    def chat_sync(
        self,
        messages: list[ChatMessage],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """同步发送聊天请求并返回模型回复。

        参数:
            messages: 对话上下文消息列表。
            temperature: 采样温度，建议范围 0~2。
            max_tokens: 最大生成 token 数，None 表示由服务端决定。

        返回:
            包含回复正文、推理内容（如有）与使用统计的 ChatResponse。

        异常:
            openai.APIError: DeepSeek API 返回错误时抛出。
        """
        body = self._build_request(messages, temperature, max_tokens, stream=False)
        response = self._openai_sync_client.chat.completions.create(**body)
        message = response.choices[0].message
        return ChatResponse(
            content=message.content or "",
            reasoning_content=getattr(message, "reasoning_content", None),
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None,
        )

    def chat_stream_sync(
        self,
        messages: list[ChatMessage],
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
    ) -> Iterator[ChatResponse]:
        """同步流式发送聊天请求，逐块返回增量内容。

        参数:
            messages: 对话上下文消息列表。
            temperature: 采样温度，建议范围 0~2。
            max_tokens: 最大生成 token 数，None 表示由服务端决定。

        返回:
            迭代器，每次产出当前增量文本的 ChatResponse。

        异常:
            openai.APIError: DeepSeek API 返回错误时抛出。
        """
        body = self._build_request(messages, temperature, max_tokens, stream=True)
        stream = self._openai_sync_client.chat.completions.create(**body)
        for chunk in stream:
            if chunk.usage is not None:
                yield ChatResponse(
                    content="",
                    reasoning_content=None,
                    model=chunk.model,
                    usage=chunk.usage.model_dump(),
                )
                continue
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            yield ChatResponse(
                content=delta.content or "",
                reasoning_content=getattr(delta, "reasoning_content", None),
                model=chunk.model,
                usage=None,
            )


def get_pro_client() -> DeepSeekClient:
    """获取 DeepSeek 思考模型客户端（默认 deepseek-v4-pro）。"""
    return DeepSeekClient(
        model=settings.deepseek_pro_model,
        enable_thinking=True,
    )


def get_flash_client() -> DeepSeekClient:
    """获取 DeepSeek 快速模型客户端（默认 deepseek-v4-flash）。"""
    return DeepSeekClient(
        model=settings.deepseek_flash_model,
        enable_thinking=False,
    )


# 模块级默认实例，便于业务层直接导入使用。
# 注意：底层 AsyncOpenAI 客户端为懒加载，导入时不会立即尝试连接或校验 API key。
deepseek_pro = get_pro_client()
deepseek_flash = get_flash_client()
