"""元数据感知的工具执行节点。

根据工具注册中心中的 ``allow_parallel`` 元数据决定并发/串行执行策略，
并在单个工具失败时返回错误 ToolMessage，避免整个图崩溃。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain.tools import ToolRuntime
from langgraph.runtime import Runtime

from echomemory_backend.ai.graphs.conversation.state import AIConversationState
from echomemory_backend.ai.tools.registry import (
    ToolRegistry,
    ToolResolutionContext,
)

logger = logging.getLogger(__name__)


def build_tool_node(registry: ToolRegistry):
    """构造一个元数据感知的工具执行节点。

    参数:
        registry: 工具注册中心，用于按名称查找工具及其元数据。

    返回:
        可在 StateGraph 中使用的节点函数。
    """

    def _serialize_tool_result(result: Any) -> str:
        """把工具结果转换为稳定、可供模型读取的文本。"""
        if result is None:
            return ""
        if isinstance(result, str):
            return result
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return str(result)

    async def _execute_tool_call(
        tool_call: dict,
        state: AIConversationState,
        context: ToolResolutionContext,
        config: RunnableConfig | None,
        graph_runtime: Runtime,
    ) -> ToolMessage:
        """执行单个工具调用并返回 ToolMessage。"""
        name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")

        if not registry.is_registered(name):
            logger.error("Tool '%s' is not registered", name)
            return ToolMessage(
                content=f"工具 '{name}' 当前不可用。",
                tool_call_id=tool_call_id,
                name=name,
            )

        if registry.resolve_tool(name, context) is None:
            logger.warning("Tool '%s' is not allowed in current context", name)
            return ToolMessage(
                content=f"工具 '{name}' 当前不可用。",
                tool_call_id=tool_call_id,
                name=name,
            )

        try:
            tool_runtime = ToolRuntime(
                state=state,
                context=graph_runtime.context,
                config=config or {},
                stream_writer=graph_runtime.stream_writer,
                tool_call_id=tool_call_id,
                store=graph_runtime.store,
                tools=registry.list_tools(),
                execution_info=graph_runtime.execution_info,
                server_info=graph_runtime.server_info,
            )
            invocation = {
                "name": name,
                "args": {**args, "runtime": tool_runtime},
                "id": tool_call_id,
                "type": "tool_call",
            }
            result = await registry.ainvoke(name, invocation, config=config)
            if isinstance(result, ToolMessage):
                if result.name is None:
                    result.name = name
                return result
            return ToolMessage(
                content=_serialize_tool_result(result),
                tool_call_id=tool_call_id,
                name=name,
            )
        except Exception:
            logger.exception("Tool '%s' execution failed", name)
            return ToolMessage(
                content=f"工具 '{name}' 执行失败，请稍后重试。",
                tool_call_id=tool_call_id,
                name=name,
            )

    async def tool_node(
        state: AIConversationState,
        config: RunnableConfig,
        runtime: Runtime | None = None,
    ) -> AIConversationState:
        """读取最后一条 AI 消息的 tool_calls 并执行对应工具。"""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage):
            return {"messages": []}

        tool_calls = getattr(last_message, "tool_calls", None) or []
        if not tool_calls:
            return {"messages": []}

        context = ToolResolutionContext(
            user_id=state.get("user_id"),
            read_only=bool(state.get("read_only", False)),
        )
        graph_runtime = runtime or Runtime()

        # 只要有任意一个工具不允许并发，就整体串行执行，保证状态安全。
        allow_parallel = all(
            registry.get_metadata(tc.get("name", "")).allow_parallel
            for tc in tool_calls
            if registry.is_registered(tc.get("name", ""))
        )

        if allow_parallel:
            results = await asyncio.gather(
                *(
                    _execute_tool_call(
                        tc,
                        state,
                        context,
                        config,
                        graph_runtime,
                    )
                    for tc in tool_calls
                )
            )
        else:
            results = []
            for tc in tool_calls:
                results.append(
                    await _execute_tool_call(
                        tc,
                        state,
                        context,
                        config,
                        graph_runtime,
                    )
                )

        return {"messages": results}

    return tool_node
