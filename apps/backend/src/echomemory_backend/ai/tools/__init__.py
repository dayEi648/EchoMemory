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
from echomemory_backend.ai.tools.music_catalog import (
    confirm_collection_change,
    get_personal_music_context,
    push_album_cards,
    push_music_cards,
    push_playlist_cards,
    request_album_collection_change,
    request_music_collection_change,
    request_playlist_collection_change,
    search_album_catalog,
    search_music_catalog,
    search_playlist_catalog,
)

# 全局默认注册表，启动时即挂载所有可用工具。
_default_registry = get_tool_registry()
_default_registry.register(
    search_web,
    read_only=True,
    allow_parallel=True,
    tags=["search", "web"],
)
for _catalog_tool in (
    search_music_catalog,
    search_playlist_catalog,
    search_album_catalog,
    get_personal_music_context,
):
    _default_registry.register(
        _catalog_tool,
        read_only=True,
        allow_parallel=True,
        tags=["search", "music-platform"],
    )

for _push_tool in (
    push_music_cards,
    push_playlist_cards,
    push_album_cards,
):
    _default_registry.register(
        _push_tool,
        read_only=True,
        allow_parallel=False,
        tags=["push", "music-platform"],
    )

for _confirmation_request_tool in (
    request_music_collection_change,
    request_playlist_collection_change,
    request_album_collection_change,
):
    _default_registry.register(
        _confirmation_request_tool,
        read_only=False,
        allow_parallel=False,
        tags=["collection", "confirmation", "music-platform"],
    )

_default_registry.register(
    confirm_collection_change,
    read_only=False,
    allow_parallel=False,
    max_concurrency=1,
    tags=["collection", "confirmation", "music-platform"],
)

__all__ = [
    "ToolMetadata",
    "ToolRegistry",
    "ToolResolutionContext",
    "get_tool_registry",
    "search_web",
    "search_music_catalog",
    "search_playlist_catalog",
    "search_album_catalog",
    "push_music_cards",
    "push_playlist_cards",
    "push_album_cards",
    "request_music_collection_change",
    "request_playlist_collection_change",
    "request_album_collection_change",
    "confirm_collection_change",
    "get_personal_music_context",
]
