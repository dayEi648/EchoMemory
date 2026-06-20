"""AI 工具注册中心。

提供工具元数据封装、统一注册与动态解析能力，支撑读写分离、并发控制、
按用户状态过滤等后续扩展。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Iterable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class ToolMetadata:
    """工具元数据。

    属性:
        name: 工具名称；默认从被装饰函数/Tool 名称取得。
        description: 工具描述；默认留空，由 ``@tool`` 的 docstring 提供。
        read_only: 是否为只读工具（不修改系统状态）。
        allow_parallel: 是否允许在一次 tool_calls 中与其它允许并行的工具并发执行。
        max_concurrency: 该工具自身的最大并发数；None 表示不限制。
        tags: 不可变能力标签集合，用于按场景过滤。
    """

    name: str
    description: str = ""
    read_only: bool = True
    allow_parallel: bool = True
    max_concurrency: int | None = None
    tags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """校验工具元数据约束。"""
        object.__setattr__(self, "tags", frozenset(self.tags))
        if not self.name:
            raise ValueError("tool metadata name cannot be empty")
        if self.max_concurrency is not None and self.max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")


@dataclass(frozen=True)
class ToolResolutionContext:
    """动态解析工具时的上下文。

    属性:
        user_id: 当前用户 ID。
        read_only: 是否仅暴露只读工具（如 MUTED/RESTRICTED 用户）。
        allowed_tags: 允许的标签集合；None 表示不限制。
    """

    user_id: int | None = None
    read_only: bool = False
    allowed_tags: set[str] | None = None


class ToolRegistry:
    """工具注册中心。

    维护工具实例到元数据的映射，支持按上下文动态过滤可用工具列表。
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._metadata: dict[str, ToolMetadata] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def register(
        self,
        tool: BaseTool,
        *,
        metadata: ToolMetadata | None = None,
        read_only: bool = True,
        allow_parallel: bool = True,
        max_concurrency: int | None = None,
        tags: Iterable[str] | None = None,
    ) -> BaseTool:
        """注册一个工具。

        参数:
            tool: 已用 ``@tool`` 装饰的工具函数或 ``BaseTool`` 实例。
            metadata: 完整的工具元数据；提供时优先使用。
            read_only: 是否为只读工具。
            allow_parallel: 是否允许并发执行。
            max_concurrency: 最大并发数。
            tags: 能力标签。

        返回:
            注册后的 BaseTool 实例。
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must be a BaseTool instance, got {type(tool)}")

        name = tool.name
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")

        if metadata is None:
            metadata = ToolMetadata(
                name=name,
                description=tool.description or "",
                read_only=read_only,
                allow_parallel=allow_parallel,
                max_concurrency=max_concurrency,
                tags=frozenset(tags or ()),
            )
        elif metadata.name != name:
            raise ValueError(
                f"Tool metadata name '{metadata.name}' does not match tool name '{name}'"
            )

        self._tools[name] = tool
        self._metadata[name] = metadata
        if metadata.max_concurrency is not None:
            self._semaphores[name] = asyncio.Semaphore(metadata.max_concurrency)
        return tool

    def get(self, name: str) -> BaseTool:
        """按名称获取工具实例。

        异常:
            KeyError: 工具未注册。
        """
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' is not registered") from exc

    def get_metadata(self, name: str) -> ToolMetadata:
        """按名称获取工具元数据。"""
        try:
            return self._metadata[name]
        except KeyError as exc:
            raise KeyError(f"Metadata for tool '{name}' is not registered") from exc

    def list_tools(self) -> list[BaseTool]:
        """返回所有已注册工具。"""
        return list(self._tools.values())

    def resolve_tools(self, context: ToolResolutionContext | None = None) -> list[BaseTool]:
        """根据上下文动态解析当前可用的工具列表。

        过滤规则：
        - ``read_only=True`` 时排除所有非只写（write）工具。
        - ``allowed_tags`` 非空时，工具至少拥有一个允许标签才会暴露。
        """
        context = context or ToolResolutionContext()
        result: list[BaseTool] = []
        for name, tool in self._tools.items():
            meta = self._metadata[name]
            if context.read_only and not meta.read_only:
                continue
            if context.allowed_tags and not set(meta.tags) & context.allowed_tags:
                continue
            result.append(tool)
        return result

    def resolve_tool(
        self,
        name: str,
        context: ToolResolutionContext | None = None,
    ) -> BaseTool | None:
        """按当前上下文解析单个工具，不可用时返回 None。"""
        if name not in self._tools:
            return None

        context = context or ToolResolutionContext()
        metadata = self._metadata[name]
        if context.read_only and not metadata.read_only:
            return None
        if context.allowed_tags and not metadata.tags & context.allowed_tags:
            return None
        return self._tools[name]

    async def ainvoke(
        self,
        name: str,
        args: dict[str, Any],
        *,
        config: RunnableConfig | None = None,
    ) -> Any:
        """执行已注册工具，并应用该工具的最大并发限制。

        参数:
            name: 工具名称。
            args: 工具参数。
            config: 当前 LangChain 运行配置。

        返回:
            工具原始返回值。

        异常:
            KeyError: 工具未注册。
        """
        tool = self.get(name)
        semaphore = self._semaphores.get(name)
        if semaphore is None:
            return await tool.ainvoke(args, config=config)

        async with semaphore:
            return await tool.ainvoke(args, config=config)

    def is_registered(self, name: str) -> bool:
        """检查工具是否已注册。"""
        return name in self._tools


# 全局默认注册表，供应用启动时统一挂载工具。
_default_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """返回全局默认工具注册表（懒加载单例）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
    return _default_registry
