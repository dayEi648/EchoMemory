"""数据库会话管理模块。

提供 SQLAlchemy 同步与异步数据库引擎及会话工厂，
供 Alembic 迁移、测试初始化和应用运行时使用。
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from echomemory_backend.core.config import settings

# 同步引擎（供 Alembic 与测试初始化使用）
sync_engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# 异步引擎（供应用运行时使用）
async_engine = create_async_engine(
    settings.async_database_url, pool_pre_ping=True, future=True
)
AsyncSessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=async_engine
)
