"""DeepSeek LLM 基础设施测试。

本模块仅验证配置加载、客户端构造与请求封装逻辑，不调用真实 DeepSeek API。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from echomemory_backend.core.config import settings
from echomemory_backend.core.llm import (
    DEFAULT_TEMPERATURE,
    REASONING_EFFORT,
    THINKING_EXTRA_BODY,
    ChatMessage,
    ChatResponse,
    DeepSeekClient,
    deepseek_flash,
    deepseek_pro,
    get_flash_client,
    get_pro_client,
)


def test_settings_loads_deepseek_defaults():
    """配置应加载 DeepSeek 默认值。"""
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.deepseek_pro_model == "deepseek-v4-pro"
    assert settings.deepseek_flash_model == "deepseek-v4-flash"
    assert settings.deepseek_default_temperature == 0.7
    assert settings.deepseek_default_timeout == 60.0
    assert settings.deepseek_reasoning_effort == "high"
    assert settings.deepseek_thinking_type == "enabled"


def test_default_clients_use_configured_models():
    """默认客户端应使用配置中的模型名称与思考模式。"""
    assert deepseek_pro.model == "deepseek-v4-pro"
    assert deepseek_pro._enable_thinking is True
    assert deepseek_flash.model == "deepseek-v4-flash"
    assert deepseek_flash._enable_thinking is False


def test_factory_functions_return_fresh_clients():
    """工厂函数每次返回新的客户端实例，但配置保持一致。"""
    pro = get_pro_client()
    flash = get_flash_client()
    assert pro is not deepseek_pro
    assert flash is not deepseek_flash
    assert pro.model == "deepseek-v4-pro"
    assert flash.model == "deepseek-v4-flash"


def test_deepseek_client_requires_model():
    """空模型应触发 ValueError。"""
    with pytest.raises(ValueError):
        DeepSeekClient(model="")


def test_pro_request_enables_thinking():
    """思考模型请求体应包含 reasoning_effort 与 extra_body。"""
    client = DeepSeekClient(model="deepseek-v4-pro", enable_thinking=True)
    messages = [ChatMessage(role="user", content="你好")]
    body = client._build_request(messages, temperature=DEFAULT_TEMPERATURE, max_tokens=512, stream=False)

    assert body["model"] == "deepseek-v4-pro"
    assert body["reasoning_effort"] == REASONING_EFFORT
    assert body["extra_body"] == THINKING_EXTRA_BODY


def test_flash_request_disables_thinking():
    """快速模型请求体不应包含 thinking 相关参数。"""
    client = DeepSeekClient(model="deepseek-v4-flash", enable_thinking=False)
    messages = [ChatMessage(role="user", content="你好")]
    body = client._build_request(messages, temperature=DEFAULT_TEMPERATURE, max_tokens=256, stream=False)

    assert body["model"] == "deepseek-v4-flash"
    assert "reasoning_effort" not in body
    assert "extra_body" not in body


async def test_chat_returns_parsed_response():
    """非流式请求应返回解析后的 ChatResponse。"""
    client = DeepSeekClient(model="deepseek-v4-pro", api_key="test-key", enable_thinking=True)

    message = MagicMock()
    message.content = "你好"
    message.reasoning_content = "正在思考"
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.model_dump.return_value = {"prompt_tokens": 3, "completion_tokens": 2}
    response = MagicMock()
    response.choices = [choice]
    response.model = "deepseek-v4-pro"
    response.usage = usage

    with patch.object(
        client._openai_client.chat.completions, "create", new=AsyncMock(return_value=response)
    ):
        result = await client.chat([ChatMessage(role="user", content="你好")])

    assert isinstance(result, ChatResponse)
    assert result.content == "你好"
    assert result.reasoning_content == "正在思考"
    assert result.model == "deepseek-v4-pro"
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 2}


async def test_chat_stream_yields_chunks():
    """流式请求应逐块产出增量内容。"""
    client = DeepSeekClient(model="deepseek-v4-flash", api_key="test-key")

    chunk1 = MagicMock()
    chunk1.choices = [MagicMock()]
    chunk1.choices[0].delta = MagicMock(content="你", reasoning_content=None)
    chunk1.model = "deepseek-v4-flash"
    chunk2 = MagicMock()
    chunk2.choices = [MagicMock()]
    chunk2.choices[0].delta = MagicMock(content="好", reasoning_content=None)
    chunk2.model = "deepseek-v4-flash"

    async def _fake_stream():
        for c in [chunk1, chunk2]:
            yield c

    with patch.object(
        client._openai_client.chat.completions,
        "create",
        new=AsyncMock(return_value=_fake_stream()),
    ):
        chunks = [c async for c in client.chat_stream([ChatMessage(role="user", content="hi")])]

    assert len(chunks) == 2
    assert chunks[0].content == "你"
    assert chunks[1].content == "好"
