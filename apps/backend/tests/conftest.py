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
from echomemory_backend.core.seed_data import get_dictionary_seed_sql
from echomemory_backend.db.base import Base
from echomemory_backend.main import app

TEST_SYNC_DATABASE_URL = os.environ["DATABASE_URL"]
TEST_ASYNC_DATABASE_URL = (
    TEST_SYNC_DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")
    .replace("postgresql://", "postgresql+asyncpg://", 1)
)

# 同步引擎（用于测试初始化、清理表结构，避免事件循环问题）
sync_test_engine = create_engine(TEST_SYNC_DATABASE_URL)


def _make_testing_sessionmaker(engine):
    """返回统一配置的异步 sessionmaker 工厂。

    关键参数与生产环境 AsyncSessionLocal 保持一致，避免测试与运行时配置漂移。
    """
    return async_sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )


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
        conn.execute(text(_TRIGGER_SQL))
    yield
    with sync_test_engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)


# 触发器 SQL（同步执行，供 setup_db 使用）
_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION fn_update_user_level()
RETURNS TRIGGER AS $$
BEGIN
    SELECT COALESCE(MAX(level), 0) INTO NEW.level
    FROM level_config
    WHERE min_exp <= NEW.exp;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_level_on_exp_change ON users;
CREATE TRIGGER trg_users_level_on_exp_change
BEFORE INSERT OR UPDATE OF exp ON users
FOR EACH ROW
EXECUTE FUNCTION fn_update_user_level();
"""

@pytest.fixture(autouse=True)
def clean_tables():
    """每次测试前清理业务数据表并重新灌入字典种子数据。"""
    with sync_test_engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE user_follows, users, musics, music_authors, music_instruments,
            music_emotion_tags, music_interest_tags, styles, languages,
            instruments, emotion_tags, interest_tags, albums, album_authors, album_musics,
            album_emotion_tags, album_interest_tags, playlists, playlist_musics,
            playlist_emotion_tags, playlist_interest_tags, comments, comment_likes,
            comment_dislikes, space_posts, space_post_images, space_post_likes,
            play_history, user_music_releases,
            user_album_collections, user_playlist_collections,
            user_emotion_tags, user_interest_tags,
            notifications, conversations, direct_messages, user_blocks
            RESTART IDENTITY CASCADE
        """))
        conn.execute(text(get_dictionary_seed_sql()))
    yield


@pytest_asyncio.fixture
async def db_session():
    """提供一个绑定到当前事件循环的异步 Session（供测试 helper 使用）。"""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL)
    AsyncTestingSessionLocal = _make_testing_sessionmaker(engine)
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


@pytest_asyncio.fixture
async def client(fake_redis):
    """TestClient 使用独立的异步 Session，避免与 pytest fixture 事件循环冲突。"""
    engine = create_async_engine(TEST_ASYNC_DATABASE_URL)
    AsyncTestingSessionLocal = _make_testing_sessionmaker(engine)

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
    await engine.dispose()
