"""数据库日志处理器与队列监听器。

使用标准库 logging.handlers.QueueHandler + QueueListener 将日志落库操作
放到独立后台线程执行，避免阻塞主事件循环；并通过失败计数器防止 DB 故障时
产生递归日志风暴。
"""

import json
import logging
import logging.handlers
import queue
import threading
import traceback
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from echomemory_backend.core.config import settings
from echomemory_backend.core.logging.context import get_log_context
from echomemory_backend.models.system_log import SystemLog

MAX_RESPONSE_BODY_CHARS = 4 * 1024
MAX_REQUEST_BODY_CHARS = 8 * 1024
MAX_FAILURES_BEFORE_DISABLE = 5

_failure_count = 0
_failure_lock = threading.Lock()

_listener: logging.handlers.QueueListener | None = None
_queue_handler: logging.handlers.QueueHandler | None = None


class _PreservingQueueHandler(logging.handlers.QueueHandler):
    """自定义 QueueHandler，在序列化前保留格式化后的堆栈信息。"""

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        if record.exc_info:
            # QueueHandler 默认会把 traceback 合并进 msg 并清空 exc_info，
            # 这里先把格式化后的堆栈保存到自定义属性，便于 DBLogHandler 提取。
            record.stack_trace_text = "".join(  # type: ignore[attr-defined]
                traceback.format_exception(*record.exc_info)
            )
        return super().prepare(record)


class ContextFilter(logging.Filter):
    """在 LogRecord 进入队列前附加当前请求上下文。"""

    def filter(self, record: logging.LogRecord) -> bool:
        context = get_log_context()
        record.request_method = context.get("method")  # type: ignore[attr-defined]
        record.request_path = context.get("path")  # type: ignore[attr-defined]
        record.request_body = context.get("request_body")  # type: ignore[attr-defined]
        record.response_body = context.get("response_body")  # type: ignore[attr-defined]
        return True


class DBLogHandler(logging.Handler):
    """同步数据库日志处理器，使用独立同步 SQLAlchemy 会话写入 system_logs。"""

    def __init__(self, sync_engine: Any) -> None:
        super().__init__()
        self.sync_engine = sync_engine
        self._session_factory = sessionmaker(bind=sync_engine)

    def emit(self, record: logging.LogRecord) -> None:
        global _failure_count

        if _failure_count >= MAX_FAILURES_BEFORE_DISABLE:
            return

        try:
            self._emit(record)
            with _failure_lock:
                _failure_count = 0
        except Exception:
            # 日志落库失败时不能抛出，也不能调用 logger 避免递归
            with _failure_lock:
                _failure_count += 1

    def _emit(self, record: logging.LogRecord) -> None:
        stack_trace: str | None = None
        if record.exc_info:
            stack_trace = "".join(traceback.format_exception(*record.exc_info))
        elif getattr(record, "stack_trace_text", None):
            stack_trace = record.stack_trace_text  # type: ignore[attr-defined]

        request_body = getattr(record, "request_body", None)
        response_body = getattr(record, "response_body", None)

        extra: dict[str, Any] = {}
        for key in ("request_method", "request_path"):
            value = getattr(record, key, None)
            if value is not None:
                extra[key] = value

        log = SystemLog(
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            stack_trace=stack_trace,
            request_method=getattr(record, "request_method", None),
            request_path=getattr(record, "request_path", None),
            request_body=_safe_truncate(request_body, MAX_REQUEST_BODY_CHARS),
            response_body=_safe_truncate(response_body, MAX_RESPONSE_BODY_CHARS),
            extra=json.dumps(extra, ensure_ascii=False) if extra else None,
        )

        session = self._session_factory()
        try:
            session.add(log)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


def _safe_truncate(value: Any, max_length: int) -> str | None:
    """将值转为字符串并截断到最大长度；非字符串类型返回 None。"""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if len(value) <= max_length:
        return value
    return value[:max_length] + "\n... [truncated]"


def setup_logging() -> None:
    """初始化数据库日志队列处理器与监听器。

    注册到根日志器，级别为 WARNING；重复调用会被忽略。
    """
    global _listener, _queue_handler

    if _queue_handler is not None:
        return

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(-1)

    sync_engine = create_engine(settings.database_url, poolclass=NullPool)
    db_handler = DBLogHandler(sync_engine)
    db_handler.setLevel(logging.WARNING)

    _listener = logging.handlers.QueueListener(
        log_queue, db_handler, respect_handler_level=True
    )
    _listener.start()

    _queue_handler = _PreservingQueueHandler(log_queue)
    _queue_handler.setLevel(logging.WARNING)
    _queue_handler.addFilter(ContextFilter())

    root_logger = logging.getLogger()
    root_logger.addHandler(_queue_handler)
    if root_logger.level > logging.WARNING or root_logger.level == logging.NOTSET:
        root_logger.setLevel(logging.WARNING)


def shutdown_logging() -> None:
    """关闭日志监听器并排空队列。"""
    global _listener, _queue_handler

    root_logger = logging.getLogger()
    if _queue_handler is not None:
        root_logger.removeHandler(_queue_handler)
        _queue_handler = None

    if _listener is not None:
        _listener.stop()
        _listener = None
