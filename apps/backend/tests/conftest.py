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
    yield
    with sync_test_engine.begin() as conn:
        Base.metadata.drop_all(bind=conn)


# 字典表种子数据 SQL（同步执行，供 setup_db 和 clean_tables 复用）
_DICTIONARY_SEED_SQL = """
INSERT INTO level_config (level, min_exp, title) VALUES
    (0, 0, '静默之声'),
    (1, 100, '初响'),
    (2, 300, '浅唱'),
    (3, 700, '低吟'),
    (4, 1500, '和鸣'),
    (5, 3000, '共鸣'),
    (6, 5500, '弦歌'),
    (7, 9500, '高歌'),
    (8, 16000, '咏叹'),
    (9, 28000, '天籁'),
    (10, 50000, '回响')
ON CONFLICT (level) DO UPDATE SET
    min_exp = EXCLUDED.min_exp,
    title = EXCLUDED.title;

INSERT INTO styles (name) VALUES
    ('流行'), ('摇滚'), ('古典'), ('电子'), ('民谣'),
    ('爵士'), ('R&B'), ('嘻哈'), ('轻音乐'), ('古风'),
    ('金属'), ('蓝调')
ON CONFLICT (name) DO NOTHING;

INSERT INTO languages (name) VALUES
    ('汉语'), ('英语'), ('日语'), ('韩语'), ('粤语'),
    ('法语'), ('西班牙语'), ('德语'), ('俄语'), ('意大利语')
ON CONFLICT (name) DO NOTHING;

INSERT INTO emotion_tags (name) VALUES
    ('治愈'), ('激昂'), ('忧伤'), ('浪漫'), ('宁静'),
    ('怀旧'), ('欢快'), ('孤独'), ('希望'), ('慵懒'),
    ('紧张'), ('温暖')
ON CONFLICT (name) DO NOTHING;

INSERT INTO interest_tags (name) VALUES
    ('运动'), ('学习'), ('睡眠'), ('通勤'), ('聚会'),
    ('阅读'), ('游戏'), ('冥想'), ('旅行'), ('工作'),
    ('烹饪'), ('散步')
ON CONFLICT (name) DO NOTHING;
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
            play_history, user_music_releases, user_music_collections,
            user_album_collections, user_playlist_collections,
            user_emotion_tags, user_interest_tags
            RESTART IDENTITY CASCADE
        """))
        conn.execute(text(_DICTIONARY_SEED_SQL))
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
