"""系统日志持久化与管理员查询接口测试。"""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.logging.context import set_log_context
from echomemory_backend.core.logging.handler import (
    ContextFilter,
    DBLogHandler,
    _PreservingQueueHandler,
)
from echomemory_backend.core.security.security import create_access_token
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.system_log import SystemLog
from echomemory_backend.models.user import User
from echomemory_backend.schemas.system_log import SystemLogListParams
from echomemory_backend.services import log_service
from tests.api_helpers import api_data

BASE = "/api/v1/admin/logs"


async def _create_user(
    db: AsyncSession,
    username: str,
    password: str = "secret",
    role: int = UserRole.USER.value,
) -> User:
    from echomemory_backend.core.security.security import get_password_hash

    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=username.capitalize(),
        role=role,
        status=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


class TestDBLogHandler:
    """测试同步数据库日志处理器。"""

    @pytest.fixture
    def sync_log_engine(self):
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        engine = create_engine(settings.database_url, poolclass=NullPool)
        yield engine
        engine.dispose()

    def _session(self, engine):
        return sessionmaker(bind=engine)()

    def test_emit_warning_creates_log(self, sync_log_engine):
        """WARNING 级别日志应写入 system_logs 表。"""
        handler = DBLogHandler(sync_log_engine)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="test warning message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)

        session = self._session(sync_log_engine)
        try:
            log = session.execute(
                select(SystemLog).where(SystemLog.message == "test warning message")
            ).scalar_one()
            assert log.level == "WARNING"
            assert log.logger == "test.logger"
            assert log.stack_trace is None
        finally:
            session.close()

    def test_emit_exception_creates_log_with_stack(self, sync_log_engine):
        """带异常的日志应写入堆栈信息。"""
        handler = DBLogHandler(sync_log_engine)
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = logging.sys.exc_info()
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="test error message",
                args=(),
                exc_info=exc_info,
            )

        handler.emit(record)

        session = self._session(sync_log_engine)
        try:
            log = session.execute(
                select(SystemLog).where(SystemLog.message == "test error message")
            ).scalar_one()
            assert log.level == "ERROR"
            assert log.stack_trace is not None
            assert "ValueError" in log.stack_trace
        finally:
            session.close()

    def test_emit_with_context(self, sync_log_engine):
        """携带请求上下文的日志应记录请求信息。"""
        set_log_context(
            method="POST",
            path="/api/v1/test",
            request_body='{"foo":"bar"}',
            response_body='{"ok":true}',
        )
        handler = DBLogHandler(sync_log_engine)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="context warning",
            args=(),
            exc_info=None,
        )
        ContextFilter().filter(record)
        handler.emit(record)

        session = self._session(sync_log_engine)
        try:
            log = session.execute(
                select(SystemLog).where(SystemLog.message == "context warning")
            ).scalar_one()
            assert log.request_method == "POST"
            assert log.request_path == "/api/v1/test"
            assert log.request_body == '{"foo":"bar"}'
        finally:
            session.close()

    def test_preserving_queue_handler_keeps_stack_trace(self, sync_log_engine):
        """QueueHandler 序列化后仍应保留堆栈信息。"""
        import queue as queue_module

        log_queue: queue_module.Queue[logging.LogRecord] = queue_module.Queue(-1)
        db_handler = DBLogHandler(sync_log_engine)
        listener = logging.handlers.QueueListener(log_queue, db_handler)
        listener.start()

        queue_handler = _PreservingQueueHandler(log_queue)
        queue_handler.setLevel(logging.WARNING)

        root = logging.getLogger()
        root.addHandler(queue_handler)

        try:
            try:
                raise ValueError("queue boom")
            except ValueError:
                exc_info = logging.sys.exc_info()
                record = logging.LogRecord(
                    name="test.queue.logger",
                    level=logging.ERROR,
                    pathname="",
                    lineno=0,
                    msg="queue error",
                    args=(),
                    exc_info=exc_info,
                )
                queue_handler.emit(record)

            import time

            time.sleep(0.5)
        finally:
            root.removeHandler(queue_handler)
            listener.stop()

        session = self._session(sync_log_engine)
        try:
            log = session.execute(
                select(SystemLog).where(SystemLog.message.ilike("%queue error%"))
            ).scalar_one()
            assert log.stack_trace is not None
            assert "ValueError" in log.stack_trace
        finally:
            session.close()


class TestLogService:
    """测试日志业务服务。"""

    async def test_list_logs_pagination(self, db_session: AsyncSession):
        """分页查询返回正确总数与列表。"""
        for i in range(5):
            db_session.add(
                SystemLog(
                    level="WARNING",
                    logger="test",
                    message=f"msg-{i}",
                )
            )
        await db_session.commit()

        params = SystemLogListParams(limit=2, offset=0)
        items, total = await log_service.list_logs(db_session, params)
        assert total == 5
        assert len(items) == 2

    async def test_list_logs_filter_by_level(self, db_session: AsyncSession):
        """按等级筛选应生效。"""
        db_session.add(SystemLog(level="WARNING", logger="test", message="warn"))
        db_session.add(SystemLog(level="ERROR", logger="test", message="err"))
        await db_session.commit()

        params = SystemLogListParams(level="ERROR")
        items, total = await log_service.list_logs(db_session, params)
        assert total == 1
        assert items[0].message == "err"

    async def test_list_logs_filter_by_time(self, db_session: AsyncSession):
        """按时间范围筛选应生效。"""
        now = datetime.now(timezone.utc)
        old = SystemLog(level="WARNING", logger="test", message="old")
        old.created_at = now - timedelta(days=2)
        new = SystemLog(level="WARNING", logger="test", message="new")
        new.created_at = now
        db_session.add(old)
        db_session.add(new)
        await db_session.commit()

        params = SystemLogListParams(start_time=now - timedelta(hours=1))
        items, total = await log_service.list_logs(db_session, params)
        assert total == 1
        assert items[0].message == "new"

    async def test_get_log_not_found(self, db_session: AsyncSession):
        """查询不存在的日志应抛出 404。"""
        with pytest.raises(BusinessError):
            await log_service.get_log(db_session, 999999)


class TestAdminLogEndpoints:
    """测试管理员日志 API 端点。"""

    async def test_admin_list_logs_success(self, client: TestClient, db_session: AsyncSession):
        """管理员可成功获取日志列表。"""
        admin = await _create_user(db_session, "admin_logs", role=UserRole.ADMIN.value)
        db_session.add(SystemLog(level="ERROR", logger="test", message="endpoint error"))
        await db_session.commit()

        resp = client.get(BASE, headers=_auth_header(admin))
        assert resp.status_code == 200
        data = api_data(resp)
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert any(item["message"] == "endpoint error" for item in data["items"])

    async def test_admin_list_logs_forbidden_for_normal_user(
        self, client: TestClient, db_session: AsyncSession
    ):
        """普通用户访问日志接口应返回 403。"""
        user = await _create_user(db_session, "normal_logs")
        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 403

    async def test_admin_get_log_detail(self, client: TestClient, db_session: AsyncSession):
        """管理员可获取单条日志详情。"""
        admin = await _create_user(db_session, "admin_log_detail", role=UserRole.ADMIN.value)
        log = SystemLog(level="CRITICAL", logger="test", message="critical detail", stack_trace="trace")
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        resp = client.get(f"{BASE}/{log.id}", headers=_auth_header(admin))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["message"] == "critical detail"
        assert data["stack_trace"] == "trace"
