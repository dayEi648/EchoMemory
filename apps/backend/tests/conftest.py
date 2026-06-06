import os
from pathlib import Path

# Load backend .env for shared credentials (password, keys, etc.)
_backend_env = Path(__file__).resolve().parent.parent / ".env"
if _backend_env.exists():
    with open(_backend_env, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key not in os.environ:
                os.environ[key] = value

# Force tests to use the dedicated test database.
_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres@localhost:5432/echomemory",
)
if "/echomemory_test" not in _db_url:
    os.environ["DATABASE_URL"] = _db_url.rsplit("/", 1)[0] + "/echomemory_test"

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from echomemory_backend.api.deps import get_db
from echomemory_backend.core import redis_client as rc
from echomemory_backend.db.base import Base
from echomemory_backend.main import app

TEST_SYNC_DATABASE_URL = os.environ["DATABASE_URL"]
TEST_ASYNC_DATABASE_URL = (
    TEST_SYNC_DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")
    .replace("postgresql://", "postgresql+asyncpg://", 1)
)

# 同步引擎（用于测试初始化、清理表结构，避免事件循环问题）
sync_test_engine = create_engine(TEST_SYNC_DATABASE_URL)

# Override lifespan to skip Alembic migrations during tests
@asynccontextmanager
async def testing_lifespan(app):
    yield

app.router.lifespan_context = testing_lifespan


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """使用同步引擎初始化测试数据库结构（仅一次）。"""
    with sync_test_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
    yield
    with sync_test_engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)


@pytest.fixture(autouse=True)
def clean_tables():
    """每次测试前清理用户相关表（使用同步连接，避免跨事件循环）。"""
    with sync_test_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE user_follows, users RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def db_session():
    """提供一个绑定到当前事件循环的异步 Session（供测试 helper 使用）。"""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL)
    AsyncTestingSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    AsyncTestingSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )
    session = AsyncTestingSessionLocal()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(rc, "redis_client", fake)
    yield fake


@pytest.fixture
def client(fake_redis):
    """TestClient 使用独立的异步 Session，避免与 pytest fixture 事件循环冲突。"""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL)
    AsyncTestingSessionLocal = async_sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    async def override_get_db():
        session = AsyncTestingSessionLocal()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
