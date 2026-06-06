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
# Connection details (password, host, etc.) come from .env;
# only the database name is overridden here.
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
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from echomemory_backend.api.deps import get_db
from echomemory_backend.core import redis_client as rc
from echomemory_backend.db.base import Base
from echomemory_backend.main import app

# PostgreSQL test database
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override lifespan to skip Alembic migrations during tests
@asynccontextmanager
async def testing_lifespan(app):
    yield

app.router.lifespan_context = testing_lifespan


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables(db_session):
    """Clean user-related tables before each test."""
    db_session.execute(text("TRUNCATE TABLE user_follows, users RESTART IDENTITY CASCADE"))
    db_session.commit()
    yield


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(rc, "redis_client", fake)
    yield fake
    fake.flushall()


@pytest.fixture
def client(db_session, fake_redis):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
