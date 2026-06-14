"""LangGraph AsyncPostgresSaver 生命周期管理。

提供全局 checkpointer 实例的初始化、获取与关闭，
供 LangGraph 状态图在请求处理中保存与读取 checkpoint。
"""

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from echomemory_backend.core.config import settings

logger = logging.getLogger(__name__)

_checkpointer: AsyncPostgresSaver | None = None
_pool: AsyncConnectionPool | None = None


async def setup_checkpointer() -> AsyncPostgresSaver:
    """初始化并返回 AsyncPostgresSaver 实例。

    使用独立 psycopg v3 连接池，与业务 SQLAlchemy asyncpg 引擎互不干扰。
    应用启动时应在 lifespan 中调用一次，确保 checkpoint 表已创建。

    返回:
        配置完成的 AsyncPostgresSaver 实例。
    """
    global _checkpointer, _pool

    if _checkpointer is not None:
        return _checkpointer

    conn_string = settings.postgres_conn_string
    _pool = AsyncConnectionPool(
        conn_string,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    logger.info("AsyncPostgresSaver initialized")
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    """获取已初始化的 AsyncPostgresSaver 实例。

    返回:
        AsyncPostgresSaver 实例。

    异常:
        RuntimeError: 尚未调用 ``setup_checkpointer`` 时抛出。
    """
    if _checkpointer is None:
        raise RuntimeError("AsyncPostgresSaver has not been initialized. Call setup_checkpointer() first.")
    return _checkpointer


async def close_checkpointer() -> None:
    """关闭 checkpointer 与底层连接池。

    应用关闭时调用，释放数据库连接。
    """
    global _checkpointer, _pool

    if _checkpointer is not None:
        await _checkpointer.aclose()
        _checkpointer = None
    if _pool is not None:
        await _pool.close()
        _pool = None
    logger.info("AsyncPostgresSaver closed")
