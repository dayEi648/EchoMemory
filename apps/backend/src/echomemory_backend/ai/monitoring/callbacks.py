"""把 LangChain / LangGraph 生命周期投影为通用 Agent 事件。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler

from echomemory_backend.ai.monitoring.context import AgentMonitorSession

logger = logging.getLogger(__name__)


def _component_name(
    serialized: dict[str, Any] | None,
    metadata: dict[str, Any] | None = None,
    *,
    fallback: str,
) -> str:
    """从框架序列化信息中解析稳定组件名称。"""
    serialized = serialized or {}
    metadata = metadata or {}
    candidate = metadata.get("langgraph_node") or serialized.get("name")
    if candidate:
        return str(candidate)
    serialized_id = serialized.get("id")
    if isinstance(serialized_id, (list, tuple)) and serialized_id:
        return str(serialized_id[-1])
    if serialized_id:
        return str(serialized_id)
    return fallback


class AgentMonitorCallbackHandler(AsyncCallbackHandler):
    """记录 chain、LLM 与 tool 的开始、完成和错误事件。"""

    def __init__(self, monitor: AgentMonitorSession) -> None:
        self.monitor = monitor
        self._started: dict[UUID, tuple[datetime, float]] = {}
        self._component_names: dict[UUID, str] = {}

    def _start_timing(self, run_id: UUID) -> datetime:
        """保存框架 run 的开始时间。"""
        started_at = datetime.now(timezone.utc)
        self._started[run_id] = (started_at, monotonic())
        return started_at

    def _finish_timing(
        self, run_id: UUID
    ) -> tuple[datetime, datetime, int]:
        """返回开始、结束时间与毫秒耗时。"""
        ended_at = datetime.now(timezone.utc)
        started_at, started_tick = self._started.pop(
            run_id, (ended_at, monotonic())
        )
        duration_ms = max(0, round((monotonic() - started_tick) * 1000))
        return started_at, ended_at, duration_ms

    def _record(self, **kwargs: Any) -> None:
        """隔离 callback 自身异常。"""
        try:
            self.monitor.record_event(**kwargs)
        except Exception:
            logger.exception(
                "Agent monitor callback failed for event=%s",
                kwargs.get("event_type"),
            )

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录 Chain / Graph / node 开始。"""
        started_at = self._start_timing(run_id)
        component_name = _component_name(
            serialized, metadata, fallback="chain"
        )
        self._component_names[run_id] = component_name
        self._record(
            event_type="chain.started",
            component_type="chain",
            component_name=component_name,
            status="RUNNING",
            payload={"input": inputs, "tags": tags, "metadata": metadata},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
        )

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录 Chain / Graph / node 成功结束。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="chain.completed",
            component_type="chain",
            component_name=self._component_names.pop(run_id, "chain"),
            status="SUCCEEDED",
            payload={"output": outputs, "tags": tags},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录 Chain / Graph / node 错误。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="chain.failed",
            component_type="chain",
            component_name=self._component_names.pop(run_id, "chain"),
            status="FAILED",
            payload={"tags": tags},
            error={"type": type(error).__name__, "message": str(error)},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[Any]],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录聊天模型实际收到的消息。"""
        started_at = self._start_timing(run_id)
        component_name = _component_name(
            serialized, metadata, fallback="chat-model"
        )
        self._component_names[run_id] = component_name
        self._record(
            event_type="llm.started",
            component_type="llm",
            component_name=component_name,
            status="RUNNING",
            payload={
                "messages": messages,
                "tags": tags,
                "metadata": metadata,
                "invocation_params": kwargs.get("invocation_params"),
            },
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
        )

    async def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录模型聚合输出和 usage。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="llm.completed",
            component_type="llm",
            component_name=self._component_names.pop(
                run_id, "chat-model"
            ),
            status="SUCCEEDED",
            payload={"response": response, "tags": tags},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )

    async def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录模型错误。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="llm.failed",
            component_type="llm",
            component_name=self._component_names.pop(
                run_id, "chat-model"
            ),
            status="FAILED",
            payload={"tags": tags},
            error={"type": type(error).__name__, "message": str(error)},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录工具调用参数。"""
        started_at = self._start_timing(run_id)
        component_name = _component_name(
            serialized, metadata, fallback="tool"
        )
        self._component_names[run_id] = component_name
        self._record(
            event_type="tool.started",
            component_type="tool",
            component_name=component_name,
            status="RUNNING",
            payload={
                "input": inputs if inputs is not None else input_str,
                "tags": tags,
                "metadata": metadata,
            },
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
        )

    async def on_tool_end(
        self,
        output: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录工具调用结果。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="tool.completed",
            component_type="tool",
            component_name=self._component_names.pop(run_id, "tool"),
            status="SUCCEEDED",
            payload={"output": output, "tags": tags},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )

    async def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """记录工具调用错误。"""
        started_at, ended_at, duration_ms = self._finish_timing(run_id)
        self._record(
            event_type="tool.failed",
            component_type="tool",
            component_name=self._component_names.pop(run_id, "tool"),
            status="FAILED",
            payload={"tags": tags},
            error={"type": type(error).__name__, "message": str(error)},
            framework_run_id=run_id,
            framework_parent_run_id=parent_run_id,
            occurred_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
        )
