"""Agent 监控运行上下文与显式事件 API。"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from echomemory_backend.ai.monitoring.serialization import (
    serialize_monitor_value,
)
from echomemory_backend.ai.monitoring.writer import (
    AgentMonitorWriter,
    MonitorWriteOperation,
    get_monitor_writer,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """返回 timezone-aware UTC 当前时间。"""
    return datetime.now(timezone.utc)


class AgentMonitorSession:
    """一次顶层 Agent 运行的非阻塞监控句柄。"""

    def __init__(
        self,
        *,
        scenario: str,
        workflow_type: str,
        workflow_name: str,
        writer: AgentMonitorWriter | Any | None = None,
        run_id: UUID | None = None,
        trace_id: UUID | None = None,
        parent_run_id: UUID | None = None,
        workflow_version: str | None = None,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
        subject_type: str | None = None,
        subject_id: str | None = None,
        thread_id: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.writer = writer or get_monitor_writer()
        self.run_id = run_id or uuid4()
        self.trace_id = trace_id or self.run_id
        self.parent_run_id = parent_run_id
        self.scenario = scenario
        self.workflow_type = workflow_type
        self.workflow_name = workflow_name
        self.workflow_version = workflow_version
        self.actor_user_id = actor_user_id
        self.actor_username = actor_username
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.thread_id = thread_id
        self.model = model
        self.metadata = metadata
        self._sequence = 0
        self._event_count = 0
        self._tool_call_count = 0
        self._usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._started_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._lock = threading.Lock()

    def _enqueue(self, operation: MonitorWriteOperation) -> None:
        """安全入队；任何监控异常都只记录日志。"""
        try:
            self.writer.enqueue(operation)
        except Exception:
            logger.exception(
                "Failed to enqueue Agent monitor operation kind=%s run=%s",
                operation.kind,
                self.run_id,
            )

    def start(self, *, input_value: Any = None) -> UUID:
        """开始运行并返回 run_id。"""
        self._started_at = _utcnow()
        self._started_monotonic = monotonic()
        try:
            self._enqueue(
                MonitorWriteOperation(
                    kind="create_run",
                    values={
                        "id": self.run_id,
                        "trace_id": self.trace_id,
                        "parent_run_id": self.parent_run_id,
                        "scenario": self.scenario,
                        "workflow_type": self.workflow_type,
                        "workflow_name": self.workflow_name,
                        "workflow_version": self.workflow_version,
                        "actor_user_id": self.actor_user_id,
                        "actor_username": self.actor_username,
                        "subject_type": self.subject_type,
                        "subject_id": self.subject_id,
                        "thread_id": self.thread_id,
                        "status": "RUNNING",
                        "model": self.model,
                        "input": serialize_monitor_value(input_value),
                        "metadata_": serialize_monitor_value(self.metadata),
                        "started_at": self._started_at,
                    },
                )
            )
        except Exception:
            logger.exception(
                "Failed to prepare Agent monitor run start run=%s",
                self.run_id,
            )
        return self.run_id

    def record_event(
        self,
        *,
        event_type: str,
        component_type: str,
        component_name: str | None = None,
        status: str | None = None,
        payload: Any = None,
        error: Any = None,
        framework_run_id: UUID | None = None,
        framework_parent_run_id: UUID | None = None,
        occurred_at: datetime | None = None,
        ended_at: datetime | None = None,
        duration_ms: int | None = None,
    ) -> int:
        """记录一条运行事件并返回分配的 sequence。"""
        with self._lock:
            self._sequence += 1
            self._event_count += 1
            if event_type == "tool.started":
                self._tool_call_count += 1
            sequence = self._sequence

        try:
            self._enqueue(
                MonitorWriteOperation(
                    kind="create_event",
                    values={
                        "run_id": self.run_id,
                        "sequence": sequence,
                        "event_type": event_type,
                        "component_type": component_type,
                        "component_name": component_name,
                        "status": status,
                        "payload": serialize_monitor_value(payload),
                        "error": serialize_monitor_value(error),
                        "framework_run_id": framework_run_id,
                        "framework_parent_run_id": framework_parent_run_id,
                        "occurred_at": occurred_at or _utcnow(),
                        "ended_at": ended_at,
                        "duration_ms": duration_ms,
                    },
                )
            )
        except Exception:
            logger.exception(
                "Failed to prepare Agent monitor event=%s run=%s",
                event_type,
                self.run_id,
            )
        return sequence

    def complete(
        self,
        *,
        output_value: Any = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """标记运行成功完成。"""
        self._finish(
            status="SUCCEEDED",
            output_value=output_value,
            usage=usage or self._usage,
        )

    def add_usage(self, usage: dict[str, Any] | None) -> None:
        """累加一次模型调用的 token usage。"""
        if not usage:
            return
        with self._lock:
            for key in self._usage:
                value = usage.get(key)
                if isinstance(value, int) and value >= 0:
                    self._usage[key] += value

    def fail(self, error: BaseException | Any) -> None:
        """标记运行失败，不传播监控错误。"""
        error_value = (
            {
                "type": type(error).__name__,
                "message": str(error),
            }
            if isinstance(error, BaseException)
            else error
        )
        self._finish(status="FAILED", error=error_value)

    def cancel(self, reason: str = "execution cancelled") -> None:
        """标记运行被客户端断开或任务取消。"""
        self._finish(
            status="CANCELLED",
            error={"type": "Cancelled", "message": reason},
        )

    def _finish(
        self,
        *,
        status: str,
        output_value: Any = None,
        error: Any = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """统一完成运行状态更新。"""
        ended_at = _utcnow()
        duration_ms = None
        if self._started_monotonic is not None:
            duration_ms = max(
                0, round((monotonic() - self._started_monotonic) * 1000)
            )
        usage = usage or {}
        try:
            self._enqueue(
                MonitorWriteOperation(
                    kind="update_run",
                    values={
                        "id": self.run_id,
                        "status": status,
                        "output": serialize_monitor_value(output_value),
                        "error": serialize_monitor_value(error),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "event_count": self._event_count,
                        "tool_call_count": self._tool_call_count,
                        "ended_at": ended_at,
                        "duration_ms": duration_ms,
                    },
                )
            )
        except Exception:
            logger.exception(
                "Failed to prepare Agent monitor completion run=%s",
                self.run_id,
            )
