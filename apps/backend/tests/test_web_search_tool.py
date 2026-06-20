"""联网搜索工具测试。"""

import importlib
from unittest.mock import AsyncMock

import pytest
from langchain_core.tools import tool

from echomemory_backend.ai.tools.web_search import search_web
from echomemory_backend.core.config import get_settings

web_search_module = importlib.import_module(
    "echomemory_backend.ai.tools.web_search"
)


@tool
async def _fake_common_search(query: str) -> str:
    """模拟 IQS MCP 标准搜索。"""
    return f"# 搜索结果\n\nquery={query}"


@pytest.fixture
def patched_settings(monkeypatch):
    """临时配置 IQS 相关设置。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "iqs_api_key", "test-api-key")
    monkeypatch.setattr(
        settings,
        "iqs_mcp_url",
        "https://test.iqs.endpoint/mcp-servers/iqs-mcp-server-search",
    )
    monkeypatch.setattr(settings, "iqs_mcp_tool_name", "common_search")
    return settings


@pytest.mark.asyncio
async def test_search_web_schema_description():
    """search_web 的 docstring 应被注入为工具描述。"""
    assert "联网搜索" in search_web.description
    assert "query" in search_web.args


@pytest.mark.asyncio
async def test_search_web_returns_formatted_results(
    patched_settings,
    monkeypatch,
):
    """正常搜索时应返回 IQS MCP 的 Markdown 结果。"""
    load_tool = AsyncMock(return_value=_fake_common_search)
    monkeypatch.setattr(web_search_module, "_load_iqs_search_tool", load_tool)

    result = await search_web.ainvoke({"query": "测试查询"})

    assert result == "# 搜索结果\n\nquery=测试查询"
    load_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_search_web_empty_api_key(monkeypatch):
    """未配置 API key 时应返回不可用提示。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "iqs_api_key", None)

    result = await search_web.ainvoke({"query": "测试"})
    assert "联网搜索服务暂时不可用" in result


@pytest.mark.asyncio
async def test_search_web_iqs_error_handling(patched_settings, monkeypatch):
    """IQS MCP 异常时应返回不可用提示而不是抛错。"""
    monkeypatch.setattr(
        web_search_module,
        "_load_iqs_search_tool",
        AsyncMock(side_effect=RuntimeError("MCP unavailable")),
    )

    result = await search_web.ainvoke({"query": "测试查询"})

    assert "联网搜索服务暂时不可用" in result


@pytest.mark.asyncio
async def test_search_web_rejects_query_outside_mcp_limit(patched_settings):
    """IQS Search MCP 要求 query 长度为 2~500。"""
    too_short = await search_web.ainvoke({"query": "a"})
    too_long = await search_web.ainvoke({"query": "a" * 501})

    assert "2 到 500" in too_short
    assert "2 到 500" in too_long


def test_build_iqs_mcp_client_uses_official_transport_and_header(
    patched_settings,
    monkeypatch,
):
    """MCP 客户端应使用官方 Streamable HTTP 地址与 X-API-Key。"""
    captured: dict = {}

    class FakeMultiServerMCPClient:
        def __init__(self, connections):
            captured.update(connections)

    monkeypatch.setattr(
        web_search_module,
        "MultiServerMCPClient",
        FakeMultiServerMCPClient,
    )

    web_search_module._build_iqs_mcp_client()

    connection = captured["iqs_search"]
    assert connection["transport"] == "http"
    assert connection["url"] == patched_settings.iqs_mcp_url
    assert connection["headers"] == {"X-API-Key": "test-api-key"}


def test_format_mcp_text_blocks_returns_readable_markdown():
    result = web_search_module._format_mcp_result(
        [
            {"type": "text", "text": "# 搜索结果"},
            {"type": "text", "text": "第二段"},
        ]
    )

    assert result == "# 搜索结果\n\n第二段"
