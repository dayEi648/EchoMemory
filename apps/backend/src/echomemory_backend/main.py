import asyncio
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from echomemory_backend.api.envelope_middleware import ApiEnvelopeMiddleware
from echomemory_backend.api.v1.router import router as api_v1_router
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.handlers import (
    business_error_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.ai.graphs.checkpointer import close_checkpointer, setup_checkpointer
from echomemory_backend.core.clients.redis_client import redis_client
from echomemory_backend.core.utils.seed_data import seed_dictionary_tables
from echomemory_backend.db.session import AsyncSessionLocal, async_engine
from echomemory_backend.models import Base  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件：启动时自动运行 Alembic 数据库迁移并初始化字典数据。"""
    base_dir = Path(__file__).resolve().parent.parent.parent
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(base_dir),
    )
    if result.returncode != 0:
        logger.error("Alembic upgrade failed: %s", result.stderr)
        raise RuntimeError(f"Alembic upgrade failed: {result.stderr}")

    # 初始化 LangGraph Postgres Checkpointer，自动创建 checkpoints 相关表
    await setup_checkpointer()

    # 验证 Redis 连接可用，避免懒连接导致启动时无感知、运行时才爆炸
    # 增加重试机制，兼容 Redis 与后端并行启动的场景
    _REDIS_RETRY_MAX = 5
    _REDIS_RETRY_INTERVAL = 1.0
    redis_ready = False
    for attempt in range(_REDIS_RETRY_MAX):
        try:
            await redis_client.ping()
            redis_ready = True
            break
        except Exception as exc:
            logger.warning(
                "Redis 连接尝试 %d/%d 失败: %s", attempt + 1, _REDIS_RETRY_MAX, exc
            )
            if attempt < _REDIS_RETRY_MAX - 1:
                await asyncio.sleep(_REDIS_RETRY_INTERVAL)
    if not redis_ready:
        raise RuntimeError(
            f"Redis 连接失败（已重试 {_REDIS_RETRY_MAX} 次），请确认 Redis 服务已启动"
        )

    await seed_dictionary_tables()

    # 启动热度定时维护任务（每 4 小时全量重算，实现时间衰减）
    async def _hotness_maintenance_loop():
        # 启动时立即执行一次，避免冷启动热度全为 0
        try:
            async with AsyncSessionLocal() as db:
                from echomemory_backend.services.hotness_service import (
                    recalculate_all_hot,
                )
                await recalculate_all_hot(db)
        except Exception:
            logger.exception("Initial hotness calculation failed")

        while True:
            await asyncio.sleep(4 * 3600)
            try:
                async with AsyncSessionLocal() as db:
                    from echomemory_backend.services.hotness_service import (
                        recalculate_all_hot,
                    )
                    await recalculate_all_hot(db)
            except Exception:
                logger.exception("Hotness maintenance failed")

    hotness_task = asyncio.create_task(_hotness_maintenance_loop())

    # 启动每日推荐刷新定时任务（每天 6:00 UTC 全量刷新）
    async def _recommendation_refresh_loop():
        from echomemory_backend.services.recommendation_service import (
            _seconds_until_next_utc_hour,
            refresh_all_daily_and_radar_recommendations,
        )
        from echomemory_backend.services.cache_service import (
            invalidate_recommendation_caches,
        )

        while True:
            try:
                sleep_seconds = _seconds_until_next_utc_hour(6)
                await asyncio.sleep(sleep_seconds)
                async with AsyncSessionLocal() as db:
                    await refresh_all_daily_and_radar_recommendations(db)
                    await invalidate_recommendation_caches()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Recommendation refresh failed")
                # 出错后等待 5 分钟再重试，避免 tight loop
                await asyncio.sleep(300)

    recommend_task = asyncio.create_task(_recommendation_refresh_loop())

    yield

    hotness_task.cancel()
    recommend_task.cancel()
    try:
        await hotness_task
    except asyncio.CancelledError:
        pass
    try:
        await recommend_task
    except asyncio.CancelledError:
        pass
    try:
        await close_checkpointer()
    except Exception:
        logger.exception("Failed to close LangGraph checkpointer")
    try:
        await async_engine.dispose()
    except Exception:
        logger.exception("Failed to dispose database engine")
    try:
        await redis_client.close()
    except Exception:
        logger.exception("Failed to close Redis client")


app = FastAPI(
    title="echomemory backend",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# 注册全局异常处理器
app.add_exception_handler(BusinessError, business_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(ApiEnvelopeMiddleware)

app.include_router(api_v1_router, prefix="/api")
