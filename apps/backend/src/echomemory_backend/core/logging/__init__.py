"""日志持久化基础设施入口。"""

from echomemory_backend.core.logging.context import (
    get_log_context,
    set_log_context,
    update_log_context,
)
from echomemory_backend.core.logging.handler import setup_logging, shutdown_logging
from echomemory_backend.core.logging.middleware import LogContextMiddleware

__all__ = [
    "get_log_context",
    "set_log_context",
    "update_log_context",
    "setup_logging",
    "shutdown_logging",
    "LogContextMiddleware",
]
