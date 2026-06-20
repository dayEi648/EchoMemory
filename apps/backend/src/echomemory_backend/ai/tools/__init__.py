"""跨 Graph/Chain 复用的 LangChain 工具包。

工具是 AI Agent 对外采取动作的入口，拥有 AI 域独有的业务语义：
面向 LLM 的参数设计、结果格式化、歧义消解、Agent 流程监控、权限/安全过滤等。

工具可以复用 ``services/`` 中的核心领域能力（如用户鉴权、歌单 CRUD），
但不应把 AI 域逻辑强行下沉到 ``services/``，避免 Agent 服务无法独立演进。
"""

from echomemory_backend.ai.tools.registry import (
    ToolMetadata,
    ToolRegistry,
    ToolResolutionContext,
    get_tool_registry,
)
from echomemory_backend.ai.tools.web_search import search_web

# 全局默认注册表，启动时即挂载所有可用工具。
_default_registry = get_tool_registry()
_default_registry.register(
    search_web,
    read_only=True,
    allow_parallel=True,
    tags=["search", "web"],
)

__all__ = [
    "ToolMetadata",
    "ToolRegistry",
    "ToolResolutionContext",
    "get_tool_registry",
    "search_web",
]
