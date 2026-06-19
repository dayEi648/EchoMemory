"""日志上下文变量，用于在异步请求生命周期中传递请求/响应信息。"""

from contextvars import ContextVar
from typing import Any

_log_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, Any]:
    """获取当前异步上下文中的日志上下文字典。

    Returns:
        当前上下文字典；若未设置则返回空字典。
    """
    context = _log_context.get()
    return context if context is not None else {}


def set_log_context(**kwargs: Any) -> None:
    """覆盖设置当前异步上下文中的日志上下文。"""
    _log_context.set(kwargs)


def update_log_context(**kwargs: Any) -> None:
    """增量更新当前异步上下文中的日志上下文。"""
    context = get_log_context().copy()
    context.update(kwargs)
    _log_context.set(context)
