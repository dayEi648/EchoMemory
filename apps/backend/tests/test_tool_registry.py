"""工具注册中心测试。"""

import asyncio

import pytest
from langchain_core.tools import tool

from echomemory_backend.ai.tools.registry import (
    ToolMetadata,
    ToolRegistry,
    ToolResolutionContext,
)


@tool
def _read_tool(query: str) -> str:
    """只读示例工具。"""
    return f"read {query}"


@tool
def _write_tool(name: str) -> str:
    """写入示例工具。"""
    return f"write {name}"


def test_register_and_get_tool():
    registry = ToolRegistry()
    registry.register(_read_tool, read_only=True, allow_parallel=True)

    assert registry.is_registered("_read_tool")
    assert registry.get("_read_tool") is _read_tool
    meta = registry.get_metadata("_read_tool")
    assert meta.read_only is True
    assert meta.allow_parallel is True


def test_resolve_tools_without_filter():
    registry = ToolRegistry()
    registry.register(_read_tool, read_only=True)
    registry.register(_write_tool, read_only=False)

    tools = registry.resolve_tools()
    names = {t.name for t in tools}
    assert names == {"_read_tool", "_write_tool"}


def test_resolve_tools_read_only_filter():
    registry = ToolRegistry()
    registry.register(_read_tool, read_only=True)
    registry.register(_write_tool, read_only=False)

    tools = registry.resolve_tools(ToolResolutionContext(read_only=True))
    names = {t.name for t in tools}
    assert names == {"_read_tool"}


def test_resolve_tools_by_tags():
    registry = ToolRegistry()
    registry.register(_read_tool, read_only=True, tags=["search"])
    registry.register(_write_tool, read_only=False, tags=["write"])

    tools = registry.resolve_tools(
        ToolResolutionContext(allowed_tags={"search"})
    )
    names = {t.name for t in tools}
    assert names == {"_read_tool"}


def test_tool_metadata_defaults():
    meta = ToolMetadata(name="test")
    assert meta.read_only is True
    assert meta.allow_parallel is True
    assert meta.max_concurrency is None
    assert meta.tags == frozenset()


def test_tool_metadata_normalizes_tags_to_frozenset():
    meta = ToolMetadata(name="test", tags=["search", "web"])

    assert meta.tags == frozenset({"search", "web"})


def test_register_rejects_duplicate_tool_name():
    registry = ToolRegistry()
    registry.register(_read_tool)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_read_tool)


def test_register_rejects_invalid_max_concurrency():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="max_concurrency"):
        registry.register(_read_tool, max_concurrency=0)


def test_register_rejects_metadata_name_mismatch():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="metadata name"):
        registry.register(
            _read_tool,
            metadata=ToolMetadata(name="different_name"),
        )


def test_resolve_tool_rechecks_context():
    registry = ToolRegistry()
    registry.register(_write_tool, read_only=False)

    assert (
        registry.resolve_tool(
            "_write_tool",
            ToolResolutionContext(read_only=True),
        )
        is None
    )


@pytest.mark.asyncio
async def test_max_concurrency_limits_real_execution():
    active = 0
    maximum_active = 0

    @tool
    async def limited_tool(value: int) -> int:
        """并发受限的测试工具。"""
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return value

    registry = ToolRegistry()
    registry.register(limited_tool, max_concurrency=1)

    results = await asyncio.gather(
        registry.ainvoke("limited_tool", {"value": 1}),
        registry.ainvoke("limited_tool", {"value": 2}),
    )

    assert results == [1, 2]
    assert maximum_active == 1
