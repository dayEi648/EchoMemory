"""阿里云 IQS Search MCP 联网搜索工具。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langchain_mcp_adapters.client import MultiServerMCPClient

from echomemory_backend.core.config import settings

logger = logging.getLogger(__name__)

_IQS_QUERY_MIN_LENGTH = 2
_IQS_QUERY_MAX_LENGTH = 500
_cached_iqs_search_tool: BaseTool | None = None
_iqs_search_tool_lock = asyncio.Lock()


def _build_iqs_mcp_client() -> MultiServerMCPClient:
    """构造 IQS Search MCP 客户端。

    返回:
        配置了官方 Streamable HTTP 地址和 API-Key 请求头的 MCP 客户端。

    异常:
        RuntimeError: IQS API key 未配置。
    """
    if not settings.iqs_api_key:
        raise RuntimeError("IQS_API_KEY is not configured")

    return MultiServerMCPClient(
        {
            "iqs_search": {
                "transport": "http",
                "url": settings.iqs_mcp_url,
                "headers": {"X-API-Key": settings.iqs_api_key},
            }
        }
    )


async def _load_iqs_search_tool() -> BaseTool:
    """从 IQS MCP Server 加载并缓存标准搜索工具。"""
    global _cached_iqs_search_tool

    if _cached_iqs_search_tool is not None:
        return _cached_iqs_search_tool

    async with _iqs_search_tool_lock:
        if _cached_iqs_search_tool is not None:
            return _cached_iqs_search_tool

        client = _build_iqs_mcp_client()
        tools = await client.get_tools(server_name="iqs_search")
        for remote_tool in tools:
            if remote_tool.name == settings.iqs_mcp_tool_name:
                _cached_iqs_search_tool = remote_tool
                return remote_tool

    raise RuntimeError(
        f"IQS MCP tool '{settings.iqs_mcp_tool_name}' is not available"
    )


def _format_mcp_result(result: Any) -> str:
    """把 MCP 工具结果转换为可供模型读取的文本。"""
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        text_blocks = [
            block["text"]
            for block in result
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            )
        ]
        if text_blocks and len(text_blocks) == len(result):
            return "\n\n".join(text_blocks)
        return json.dumps(result, ensure_ascii=False)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


@tool
async def search_web(query: str) -> str:
    """使用联网搜索获取实时、时效性或超出内置知识范围的信息。

    当用户询问时事新闻、最新技术或产品动态、政策变化等强时效性内容，
    明确要求上网搜索，或者现有知识可能已经过时时使用此工具。

    Args:
        query: 需要搜索的问题或关键词，长度为 2 到 500 个字符。

    Returns:
        阿里云 IQS Search MCP 返回的 Markdown 搜索结果。
    """
    normalized_query = query.strip()
    if not (
        _IQS_QUERY_MIN_LENGTH
        <= len(normalized_query)
        <= _IQS_QUERY_MAX_LENGTH
    ):
        return "搜索内容长度必须在 2 到 500 个字符之间。"

    if not settings.iqs_api_key:
        logger.error("IQS_API_KEY 未配置")
        return "联网搜索服务暂时不可用。"

    try:
        remote_tool = await _load_iqs_search_tool()
        result = await remote_tool.ainvoke({"query": normalized_query})
        return _format_mcp_result(result)
    except Exception:
        logger.exception("IQS Search MCP 调用失败")
        return "联网搜索服务暂时不可用。"
