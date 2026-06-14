"""跨 Graph/Chain 复用的 LangChain 工具包。

工具是 AI Agent 对外采取动作的入口，拥有 AI 域独有的业务语义：
面向 LLM 的参数设计、结果格式化、歧义消解、Agent 流程监控、权限/安全过滤等。

工具可以复用 ``services/`` 中的核心领域能力（如用户鉴权、歌单 CRUD），
但不应把 AI 域逻辑强行下沉到 ``services/``，避免 Agent 服务无法独立演进。
当前尚未注册任何工具；后续按业务领域新增模块（如 ``music.py``、``playlist.py``），
并在此 ``__init__`` 的 ``TOOLS`` 列表中汇总，供 ``ToolNode`` 或动态发现使用。
"""

from typing import Any

TOOLS: list[Any] = []

__all__ = ["TOOLS"]
