"""当前异步执行链中的 Agent 监控上下文。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from echomemory_backend.ai.monitoring.context import AgentMonitorSession

_current_monitor: ContextVar[AgentMonitorSession | None] = ContextVar(
    "current_agent_monitor", default=None
)


def get_current_monitor() -> AgentMonitorSession | None:
    """返回当前任务绑定的监控会话。"""
    return _current_monitor.get()


@contextmanager
def bind_monitor(
    monitor: AgentMonitorSession | None,
) -> Iterator[AgentMonitorSession | None]:
    """在当前上下文中临时绑定监控会话。"""
    token = _current_monitor.set(monitor)
    try:
        yield monitor
    finally:
        _current_monitor.reset(token)

