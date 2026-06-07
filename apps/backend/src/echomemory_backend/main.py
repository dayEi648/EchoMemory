import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import select

from echomemory_backend.api.v1.router import router as api_v1_router
from echomemory_backend.core.config import settings
from echomemory_backend.core.redis_client import redis_client
from echomemory_backend.db.session import AsyncSessionLocal, async_engine
from echomemory_backend.models import Base  # noqa: F401
from echomemory_backend.models.dictionary import LevelConfig


# level_config 种子数据
_LEVEL_CONFIG_SEED = [
    LevelConfig(level=0, min_exp=0, title="静默之声"),
    LevelConfig(level=1, min_exp=100, title="初响"),
    LevelConfig(level=2, min_exp=300, title="浅唱"),
    LevelConfig(level=3, min_exp=700, title="低吟"),
    LevelConfig(level=4, min_exp=1500, title="和鸣"),
    LevelConfig(level=5, min_exp=3000, title="共鸣"),
    LevelConfig(level=6, min_exp=5500, title="弦歌"),
    LevelConfig(level=7, min_exp=9500, title="高歌"),
    LevelConfig(level=8, min_exp=16000, title="咏叹"),
    LevelConfig(level=9, min_exp=28000, title="天籁"),
    LevelConfig(level=10, min_exp=50000, title="回响"),
]


async def _seed_level_config() -> None:
    """若 level_config 为空，则灌入种子数据。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(LevelConfig))
        if result.scalar_one_or_none() is None:
            db.add_all(_LEVEL_CONFIG_SEED)
            await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件：启动时自动运行 Alembic 数据库迁移并初始化种子数据。"""
    base_dir = Path(__file__).resolve().parent.parent.parent
    alembic_cfg = Config(str(base_dir / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, command.upgrade, alembic_cfg, "head")

    await _seed_level_config()
    yield
    await async_engine.dispose()
    await redis_client.close()


app = FastAPI(title="echomemory backend", lifespan=lifespan)
app.include_router(api_v1_router, prefix="/api")
