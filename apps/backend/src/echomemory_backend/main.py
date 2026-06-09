import asyncio
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from echomemory_backend.api.v1.router import router as api_v1_router
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.core.redis_client import redis_client
from echomemory_backend.db.session import AsyncSessionLocal, async_engine
from echomemory_backend.models import Base  # noqa: F401
from echomemory_backend.models.dictionary import (
    EmotionTag,
    InterestTag,
    Language,
    LevelConfig,
    Style,
)

logger = logging.getLogger(__name__)


# 字典表种子数据（应用启动时自动灌入，若表为空）
_SEED_DATA = {
    "level_config": [
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
    ],
    "styles": [
        Style(name="流行"),
        Style(name="摇滚"),
        Style(name="古典"),
        Style(name="电子"),
        Style(name="民谣"),
        Style(name="爵士"),
        Style(name="R&B"),
        Style(name="嘻哈"),
        Style(name="轻音乐"),
        Style(name="古风"),
        Style(name="金属"),
        Style(name="蓝调"),
    ],
    "languages": [
        Language(name="汉语"),
        Language(name="英语"),
        Language(name="日语"),
        Language(name="韩语"),
        Language(name="粤语"),
        Language(name="法语"),
        Language(name="西班牙语"),
        Language(name="德语"),
        Language(name="俄语"),
        Language(name="意大利语"),
    ],
    "emotion_tags": [
        EmotionTag(name="治愈"),
        EmotionTag(name="激昂"),
        EmotionTag(name="忧伤"),
        EmotionTag(name="浪漫"),
        EmotionTag(name="宁静"),
        EmotionTag(name="怀旧"),
        EmotionTag(name="欢快"),
        EmotionTag(name="孤独"),
        EmotionTag(name="希望"),
        EmotionTag(name="慵懒"),
        EmotionTag(name="紧张"),
        EmotionTag(name="温暖"),
    ],
    "interest_tags": [
        InterestTag(name="运动"),
        InterestTag(name="学习"),
        InterestTag(name="睡眠"),
        InterestTag(name="通勤"),
        InterestTag(name="聚会"),
        InterestTag(name="阅读"),
        InterestTag(name="游戏"),
        InterestTag(name="冥想"),
        InterestTag(name="旅行"),
        InterestTag(name="工作"),
        InterestTag(name="烹饪"),
        InterestTag(name="散步"),
    ],
}


async def _seed_dictionary_tables() -> None:
    """若字典表为空，则灌入种子数据。"""
    async with AsyncSessionLocal() as db:
        for table_name, items in _SEED_DATA.items():
            model_cls = items[0].__class__
            result = await db.execute(select(model_cls))
            if result.scalars().first() is None:
                db.add_all(items)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期事件：启动时自动运行 Alembic 数据库迁移并初始化字典数据。"""
    base_dir = Path(__file__).resolve().parent.parent.parent
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=str(base_dir),
    )
    if result.returncode != 0:
        logger.error("Alembic upgrade failed: %s", result.stderr)
        raise RuntimeError(f"Alembic upgrade failed: {result.stderr}")

    await _seed_dictionary_tables()
    yield
    await async_engine.dispose()
    await redis_client.close()


app = FastAPI(title="echomemory backend", lifespan=lifespan)

# CORS 中间件：允许前端开发服务器跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    """将业务异常统一转换为 JSON 响应，确保前端能感知具体错误信息。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """统一处理 FastAPI/Starlette 抛出的 HTTPException。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """统一处理请求参数校验失败异常。"""
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request parameters"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """兜底异常处理器，避免未处理异常直接暴露内部细节。"""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(api_v1_router, prefix="/api")
