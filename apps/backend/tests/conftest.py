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

from echomemory_backend.ai import langchain as ai_langchain
from echomemory_backend.ai.clients import deepseek as deepseek_module
from echomemory_backend.ai.clients.deepseek import ChatResponse
from echomemory_backend.ai.graphs import checkpointer as ai_checkpointer
from echomemory_backend.ai.monitoring import writer as agent_monitor_writer_module
from echomemory_backend.api.deps import get_db
from echomemory_backend.core.clients import redis_client as rc
from echomemory_backend.core.utils.seed_data import get_dictionary_seed_sql
from echomemory_backend.db.base import Base
from echomemory_backend.main import app
from echomemory_backend.services import user_profile_service as user_profile_module

import echomemory_backend.models  # noqa: F401  # 确保 setup_db 创建全部 ORM 表

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
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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
            play_history, user_music_likes,
            user_album_collections, user_playlist_collections,
            user_emotion_tags, user_interest_tags,
            user_languages, user_styles,
            user_daily_recommendations, user_radar_recommendations,
            notifications, conversations, direct_messages, user_blocks,
            vector_documents, ai_conversations, system_logs, user_profiles,
            content_moderation_history, content_moderation_tasks,
            user_content_moderation_stats, agent_events, agent_runs
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
    """使用 FakeRedis 替代真实 Redis 客户端。"""
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(rc, "redis_client", fake)
    yield fake


@pytest.fixture(autouse=True)
def fake_ai_checkpointer(monkeypatch):
    """使用 MemorySaver 替代 Postgres Checkpointer，避免测试依赖真实数据库。"""
    from langgraph.checkpoint.memory import MemorySaver

    saver = MemorySaver()
    monkeypatch.setattr(ai_checkpointer, "_checkpointer", saver)
    monkeypatch.setattr(ai_checkpointer, "_pool", None)
    yield saver


@pytest.fixture(autouse=True)
def fake_agent_monitor_writer(monkeypatch):
    """测试中使用内存记录器，避免后台监控任务跨测试写库。"""

    class _FakeAgentMonitorWriter:
        def __init__(self):
            self.operations = []

        def enqueue(self, operation):
            self.operations.append(operation)
            return True

    writer = _FakeAgentMonitorWriter()
    monkeypatch.setattr(agent_monitor_writer_module, "_writer", writer)
    yield writer


@pytest.fixture(autouse=True)
def fake_deepseek_client(monkeypatch):
    """使用固定回复模拟 DeepSeekClient，避免测试调用真实 LLM API。"""

    class _FakeDeepSeekClient:
        def __init__(self, model, **kwargs):
            self.model = model
            self._enable_thinking = kwargs.get("enable_thinking", False)

        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content="你好，我是 AI 助手。",
                reasoning_content="先理解用户的问候，再简洁回应。" if self._enable_thinking else None,
                model=self.model,
            )

        async def chat_stream(self, messages, **kwargs):
            if self._enable_thinking:
                for text in ["先理解用户的", "问候，再简洁回应。"]:
                    yield ChatResponse(reasoning_content=text, content="", model=self.model)
            for text in ["你好", "，", "我是", " AI 助手。"]:
                yield ChatResponse(content=text, model=self.model)

        def chat_sync(self, messages, **kwargs):
            return ChatResponse(
                content="你好，我是 AI 助手。",
                reasoning_content="先理解用户的问候，再简洁回应。" if self._enable_thinking else None,
                model=self.model,
            )

        def chat_stream_sync(self, messages, **kwargs):
            if self._enable_thinking:
                for text in ["先理解用户的", "问候，再简洁回应。"]:
                    yield ChatResponse(reasoning_content=text, content="", model=self.model)
            for text in ["你好", "，", "我是", " AI 助手。"]:
                yield ChatResponse(content=text, model=self.model)

    monkeypatch.setattr(deepseek_module, "DeepSeekClient", _FakeDeepSeekClient)
    monkeypatch.setattr(ai_langchain.deepseek_chat, "DeepSeekClient", _FakeDeepSeekClient)
    monkeypatch.setattr(user_profile_module, "DeepSeekClient", _FakeDeepSeekClient)
    yield _FakeDeepSeekClient


@pytest.fixture
def fake_title_generator(monkeypatch):
    """固定标题生成结果，避免测试依赖真实 LLM 输出。"""
    from echomemory_backend.services import ai_conversation_service

    async def _generate(*args, **kwargs):
        return "生成的标题"

    monkeypatch.setattr(ai_conversation_service, "generate_conversation_title", _generate)
    yield _generate


@pytest_asyncio.fixture
async def client(fake_redis, fake_title_generator):
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
