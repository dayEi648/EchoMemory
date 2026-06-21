"""Agent 监控异步数据库写入队列。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from echomemory_backend.core.config import settings
from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.agent_monitor import AgentEvent, AgentRun

logger = logging.getLogger(__name__)

OperationKind = Literal["create_run", "update_run", "create_event"]


@dataclass(frozen=True)
class MonitorWriteOperation:
    """一项可重试的监控数据库写操作。"""

    kind: OperationKind
    values: dict[str, Any]


class AgentMonitorWriter:
    """使用独立会话串行持久化监控记录。"""

    def __init__(
        self,
        *,
        queue_size: int,
        max_retries: int,
        retry_base_seconds: float,
        batch_size: int = 100,
        session_factory: async_sessionmaker | None = None,
    ) -> None:
        self._queue: asyncio.Queue[MonitorWriteOperation | None] = asyncio.Queue(
            maxsize=queue_size
        )
        self._max_retries = max_retries
        self._retry_base_seconds = retry_base_seconds
        self._batch_size = batch_size
        self._session_factory = session_factory or AsyncSessionLocal
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """启动后台写入任务；重复调用无副作用。"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._worker(), name="agent-monitor-writer"
            )

    def enqueue(self, operation: MonitorWriteOperation) -> bool:
        """非阻塞地加入写队列，队列已满时记录错误并返回 False。"""
        try:
            self._queue.put_nowait(operation)
            return True
        except asyncio.QueueFull:
            logger.error(
                "Agent monitor queue is full; dropping operation kind=%s run=%s",
                operation.kind,
                operation.values.get("id") or operation.values.get("run_id"),
            )
            return False

    async def flush(self) -> None:
        """等待当前已入队操作完成，主要用于测试和受控关闭。"""
        await self._queue.join()

    async def close(self, *, timeout_seconds: float = 10.0) -> None:
        """在超时范围内排空队列并停止后台任务。"""
        if self._task is None:
            return
        try:
            await asyncio.wait_for(
                self._queue.join(), timeout=timeout_seconds
            )
        except TimeoutError:
            logger.error(
                "Timed out after %.1fs while draining Agent monitor queue; "
                "discarding %d pending operations",
                timeout_seconds,
                self._queue.qsize(),
            )
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
            return
        await self._queue.put(None)
        await self._task
        self._task = None

    async def _worker(self) -> None:
        """持续批量消费队列；写入失败不会终止 worker。"""
        while True:
            operation = await self._queue.get()
            batch: list[MonitorWriteOperation] = []
            try:
                if operation is None:
                    return
                batch.append(operation)
                while len(batch) < self._batch_size:
                    try:
                        queued = self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    if queued is None:
                        self._queue.task_done()
                        break
                    batch.append(queued)
                await self._persist_batch_with_retry(batch)
            finally:
                for _ in batch or [operation]:
                    self._queue.task_done()

    async def _persist_batch_with_retry(
        self, operations: list[MonitorWriteOperation]
    ) -> None:
        """使用有限重试批量写入操作。"""
        for attempt in range(1, self._max_retries + 1):
            try:
                await self._persist_batch(operations)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt >= self._max_retries:
                    logger.exception(
                        "Agent monitor batch write failed after %d attempts; "
                        "falling back to isolated writes for %d operations",
                        attempt,
                        len(operations),
                    )
                    for operation in operations:
                        await self._persist_with_retry(operation)
                    return
                logger.warning(
                    "Agent monitor batch write attempt %d/%d failed; retrying",
                    attempt,
                    self._max_retries,
                    exc_info=True,
                )
                await asyncio.sleep(
                    self._retry_base_seconds * (2 ** (attempt - 1))
                )

    async def _persist_with_retry(
        self, operation: MonitorWriteOperation
    ) -> None:
        """使用指数退避有限重试一项写操作。"""
        for attempt in range(1, self._max_retries + 1):
            try:
                await self._persist(operation)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt >= self._max_retries:
                    logger.exception(
                        "Agent monitor write failed after %d attempts; "
                        "dropping operation kind=%s run=%s",
                        attempt,
                        operation.kind,
                        operation.values.get("id")
                        or operation.values.get("run_id"),
                    )
                    return
                logger.warning(
                    "Agent monitor write attempt %d/%d failed; retrying kind=%s",
                    attempt,
                    self._max_retries,
                    operation.kind,
                    exc_info=True,
                )
                await asyncio.sleep(
                    self._retry_base_seconds * (2 ** (attempt - 1))
                )

    async def _persist(self, operation: MonitorWriteOperation) -> None:
        """在独立短事务中持久化单项操作。"""
        async with self._session_factory() as db:
            await self._apply_operation(db, operation)
            await db.commit()

    async def _persist_batch(
        self, operations: list[MonitorWriteOperation]
    ) -> None:
        """在一个短事务中按队列顺序写入一批操作。"""
        async with self._session_factory() as db:
            for operation in operations:
                await self._apply_operation(db, operation)
            await db.commit()

    async def _apply_operation(
        self, db: Any, operation: MonitorWriteOperation
    ) -> None:
        """把一项队列操作应用到当前事务。"""
        if operation.kind == "create_run":
            db.add(AgentRun(**operation.values))
        elif operation.kind == "create_event":
            db.add(AgentEvent(**operation.values))
        elif operation.kind == "update_run":
            values = dict(operation.values)
            run_id = values.pop("id")
            await db.execute(
                update(AgentRun)
                .where(AgentRun.id == run_id)
                .values(**values)
            )
        else:
            raise ValueError(
                f"Unsupported monitor operation: {operation.kind}"
            )


_writer: AgentMonitorWriter | None = None


def get_monitor_writer() -> AgentMonitorWriter:
    """返回进程内 Agent 监控 writer 单例。"""
    global _writer
    if _writer is None:
        _writer = AgentMonitorWriter(
            queue_size=settings.agent_monitor_queue_size,
            max_retries=settings.agent_monitor_max_retries,
            retry_base_seconds=settings.agent_monitor_retry_base_seconds,
            batch_size=settings.agent_monitor_batch_size,
        )
    return _writer


def setup_monitor_writer() -> AgentMonitorWriter:
    """初始化并启动 Agent 监控 writer。"""
    writer = get_monitor_writer()
    writer.start()
    return writer


async def close_monitor_writer() -> None:
    """排空并关闭 Agent 监控 writer。"""
    global _writer
    if _writer is not None:
        await _writer.close(
            timeout_seconds=settings.agent_monitor_shutdown_timeout_seconds
        )
        _writer = None
