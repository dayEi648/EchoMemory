"""Agent 监控基础设施测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from echomemory_backend.ai.monitoring.context import AgentMonitorSession
from echomemory_backend.ai.monitoring.callbacks import AgentMonitorCallbackHandler
from echomemory_backend.ai.monitoring.serialization import serialize_monitor_value
from echomemory_backend.ai.monitoring.writer import AgentMonitorWriter
from echomemory_backend.ai.monitoring.writer import MonitorWriteOperation
from echomemory_backend.models.agent_monitor import AgentEvent, AgentRun
from echomemory_backend.core.security.security import create_access_token
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.user import User
from tests.api_helpers import api_data


class _RecordingWriter:
    """记录入队操作的测试 writer。"""

    def __init__(self) -> None:
        self.operations: list[object] = []

    def enqueue(self, operation: object) -> bool:
        self.operations.append(operation)
        return True


class _FailingWriter:
    """模拟监控 writer 故障。"""

    def enqueue(self, operation: object) -> bool:
        raise RuntimeError("monitor queue unavailable")


def test_serialize_monitor_value_redacts_secrets_and_truncates_text():
    """监控序列化必须递归脱敏，并显式标记文本截断。"""
    value = {
        "api_key": "secret-key",
        "nested": {
            "Authorization": "Bearer secret-token",
            "content": "abcdefgh",
        },
    }

    result = serialize_monitor_value(value, max_text_length=5)

    assert result["api_key"] == "[REDACTED]"
    assert result["nested"]["Authorization"] == "[REDACTED]"
    assert result["nested"]["content"] == {
        "value": "abcde",
        "is_truncated": True,
        "original_length": 8,
    }


def test_monitor_session_assigns_stable_event_sequence():
    """同一运行内事件序号必须严格递增。"""
    writer = _RecordingWriter()
    session = AgentMonitorSession(
        writer=writer,
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
        actor_user_id=42,
    )

    session.start(input_value={"message": "hello"})
    session.record_event(
        event_type="message.received",
        component_type="message",
        component_name="human",
        payload={"content": "hello"},
    )
    session.record_event(
        event_type="prompt.rendered",
        component_type="prompt",
        component_name="system",
        payload={"content": "system prompt"},
    )

    event_operations = [
        operation
        for operation in writer.operations
        if getattr(operation, "kind", None) == "create_event"
    ]
    assert [operation.values["sequence"] for operation in event_operations] == [1, 2]


def test_monitor_session_never_propagates_writer_failure():
    """监控入队失败不得传播到 Agent 主流程。"""
    session = AgentMonitorSession(
        writer=_FailingWriter(),
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
    )

    session.start(input_value={"message": "hello"})
    session.record_event(
        event_type="graph.started",
        component_type="graph",
        component_name="conversation",
    )
    session.complete(output_value={"message": "world"})


def test_monitor_session_never_propagates_serialization_failure():
    """不可序列化的运行对象也不得影响 Agent 主流程。"""

    class _BrokenValue:
        def __repr__(self):
            raise RuntimeError("broken repr")

    writer = _RecordingWriter()
    session = AgentMonitorSession(
        writer=writer,
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
    )

    session.start(input_value=_BrokenValue())
    session.record_event(
        event_type="custom.value",
        component_type="custom",
        payload=_BrokenValue(),
    )
    session.complete(output_value=_BrokenValue())

    serialized_values = [
        operation.values
        for operation in writer.operations
    ]
    assert serialized_values[0]["input"] == "<unserializable:_BrokenValue>"


@pytest.mark.asyncio
async def test_monitor_writer_retries_without_propagating(monkeypatch):
    """数据库暂时失败时应有限重试，最终仍不得向主流程抛错。"""
    writer = AgentMonitorWriter(
        queue_size=10,
        max_retries=3,
        retry_base_seconds=0,
    )
    attempts = 0

    async def _fail_twice(operation):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary database failure")

    monkeypatch.setattr(writer, "_persist", _fail_twice)

    await writer._persist_with_retry(
        type(
            "_Operation",
            (),
            {"kind": "create_run", "values": {"id": uuid4()}},
        )()
    )

    assert attempts == 3


@pytest.mark.asyncio
async def test_monitor_writer_isolates_failed_operation_in_batch(monkeypatch):
    """批量事务失败后应隔离单项，不能连带丢弃其它运行。"""
    writer = AgentMonitorWriter(
        queue_size=10,
        max_retries=1,
        retry_base_seconds=0,
    )
    persisted: list[str] = []
    good = MonitorWriteOperation(
        kind="create_run", values={"id": "good"}
    )
    bad = MonitorWriteOperation(
        kind="create_run", values={"id": "bad"}
    )

    async def _fail_batch(operations):
        raise RuntimeError("batch failure")

    async def _persist_one(operation):
        if operation.values["id"] == "bad":
            raise RuntimeError("invalid operation")
        persisted.append(operation.values["id"])

    monkeypatch.setattr(writer, "_persist_batch", _fail_batch)
    monkeypatch.setattr(writer, "_persist", _persist_one)

    await writer._persist_batch_with_retry([good, bad])

    assert persisted == ["good"]


@pytest.mark.asyncio
async def test_monitor_writer_persists_run_event_and_completion(
    db_session: AsyncSession,
):
    """异步 writer 应按队列顺序持久化运行、事件和最终状态。"""
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
    )
    writer = AgentMonitorWriter(
        queue_size=10,
        max_retries=1,
        retry_base_seconds=0,
        session_factory=session_factory,
    )
    session = AgentMonitorSession(
        writer=writer,
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
        actor_user_id=99,
    )

    writer.start()
    run_id = session.start(input_value={"content": "hello"})
    session.record_event(
        event_type="message.received",
        component_type="message",
        component_name="human",
        status="SUCCEEDED",
        payload={"content": "hello"},
    )
    session.complete(output_value={"content": "world"})
    await writer.close()

    db_session.expire_all()
    stored_run = await db_session.get(AgentRun, run_id)
    stored_events = list(
        (
            await db_session.execute(
                select(AgentEvent).where(AgentEvent.run_id == run_id)
            )
        )
        .scalars()
        .all()
    )
    assert stored_run is not None
    assert stored_run.status == "SUCCEEDED"
    assert stored_run.output == {"content": "world"}
    assert stored_run.event_count == 1
    assert [event.sequence for event in stored_events] == [1]


@pytest.mark.asyncio
async def test_callback_handler_records_framework_lifecycle_events():
    """通用 callback 应记录 chain、LLM 和 tool 生命周期。"""
    writer = _RecordingWriter()
    session = AgentMonitorSession(
        writer=writer,
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
    )
    session.start(input_value={"message": "hello"})
    callback = AgentMonitorCallbackHandler(session)
    chain_run_id = uuid4()
    llm_run_id = uuid4()
    tool_run_id = uuid4()

    await callback.on_chain_start(
        {"name": "chatbot"},
        {"messages": ["hello"]},
        run_id=chain_run_id,
        parent_run_id=None,
        metadata={"langgraph_node": "chatbot"},
    )
    await callback.on_chain_end(
        {"messages": ["world"]},
        run_id=chain_run_id,
        parent_run_id=None,
    )
    await callback.on_chat_model_start(
        {"name": "deepseek-chat"},
        [["system", "hello"]],
        run_id=llm_run_id,
        parent_run_id=chain_run_id,
    )
    await callback.on_llm_end(
        {"generations": [["world"]]},
        run_id=llm_run_id,
        parent_run_id=chain_run_id,
    )
    await callback.on_tool_start(
        {"name": "search_music_catalog"},
        '{"query":"jazz"}',
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
        inputs={"query": "jazz"},
    )
    await callback.on_tool_end(
        {"items": []},
        run_id=tool_run_id,
        parent_run_id=chain_run_id,
    )

    event_types = [
        operation.values["event_type"]
        for operation in writer.operations
        if getattr(operation, "kind", None) == "create_event"
    ]
    assert event_types == [
        "chain.started",
        "chain.completed",
        "llm.started",
        "llm.completed",
        "tool.started",
        "tool.completed",
    ]


@pytest.mark.asyncio
async def test_agent_run_survives_hard_user_delete(db_session: AsyncSession):
    """用户被硬删除后，Agent 监控运行和事件必须完整保留。"""
    user = User(
        username="monitor_retention",
        password_hash="hash",
        nickname="Monitor",
        role=0,
        status=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id

    run_id = uuid4()
    run = AgentRun(
        id=run_id,
        trace_id=run_id,
        scenario="ai_conversation",
        workflow_type="graph",
        workflow_name="conversation",
        actor_user_id=user_id,
        actor_username=user.username,
        status="SUCCEEDED",
        started_at=datetime.now(timezone.utc),
    )
    event = AgentEvent(
        run_id=run_id,
        sequence=1,
        event_type="run.started",
        component_type="graph",
        component_name="conversation",
        status="SUCCEEDED",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add_all([run, event])
    await db_session.commit()

    await db_session.execute(delete(User).where(User.id == user_id))
    await db_session.commit()

    stored_run = await db_session.get(AgentRun, run_id)
    stored_events = list(
        (
            await db_session.execute(
                select(AgentEvent).where(AgentEvent.run_id == run_id)
            )
        )
        .scalars()
        .all()
    )

    assert stored_run is not None
    assert stored_run.actor_user_id == user_id
    assert stored_run.actor_username == "monitor_retention"
    assert len(stored_events) == 1


@pytest.mark.asyncio
async def test_ai_conversation_emits_end_to_end_monitor_timeline(
    client: TestClient,
    db_session: AsyncSession,
    fake_agent_monitor_writer,
):
    """AI 对话应把提示词、模型请求和记忆变化写入同一运行时间线。"""
    user = User(
        username="monitor_conversation",
        password_hash="hash",
        nickname="Monitor Conversation",
        role=0,
        status=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=user.id)}"
    }

    response = client.post(
        "/api/v1/ai/conversations",
        headers=headers,
        json={"first_message": "推荐一首爵士乐", "stream": False},
    )

    assert response.status_code == 201
    assert api_data(response)["ai_message"]["role"] == "ai"

    operations = fake_agent_monitor_writer.operations
    create_runs = [
        operation
        for operation in operations
        if operation.kind == "create_run"
    ]
    assert len(create_runs) == 1
    assert create_runs[0].values["scenario"] == "ai_conversation"
    assert create_runs[0].values["actor_user_id"] == user.id
    assert create_runs[0].values["actor_username"] == user.username

    event_types = [
        operation.values["event_type"]
        for operation in operations
        if operation.kind == "create_event"
    ]
    assert "prompt.initialized" in event_types
    assert "message.received" in event_types
    assert "llm.request.prepared" in event_types
    assert "llm.response.completed" in event_types
    assert "memory.short_term.updated" in event_types

    updates = [
        operation
        for operation in operations
        if operation.kind == "update_run"
    ]
    assert updates[-1].values["status"] == "SUCCEEDED"


async def _create_monitor_api_user(
    db: AsyncSession,
    username: str,
    *,
    role: int,
) -> User:
    """创建监控 API 测试用户。"""
    user = User(
        username=username,
        password_hash="hash",
        nickname=username,
        role=role,
        status=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_admin_agent_monitor_list_filters_and_cursor_paginates(
    client: TestClient,
    db_session: AsyncSession,
):
    """管理员应能按场景和用户查询，并使用稳定游标翻页。"""
    admin = await _create_monitor_api_user(
        db_session, "monitor_admin", role=UserRole.ADMIN
    )
    base_time = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc)
    runs = []
    for index in range(3):
        run_id = uuid4()
        runs.append(
            AgentRun(
                id=run_id,
                trace_id=run_id,
                scenario="ai_conversation",
                workflow_type="graph",
                workflow_name="conversation",
                actor_user_id=100,
                actor_username="deleted_user",
                status="SUCCEEDED",
                model="deepseek-v4-flash",
                started_at=base_time.replace(minute=index),
                event_count=index + 1,
            )
        )
    other_id = uuid4()
    runs.append(
        AgentRun(
            id=other_id,
            trace_id=other_id,
            scenario="comment_agent",
            workflow_type="chain",
            workflow_name="comment_review",
            actor_user_id=200,
            status="FAILED",
            started_at=base_time,
        )
    )
    db_session.add_all(runs)
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=admin.id)}"
    }

    first_response = client.get(
        "/api/v1/admin/agent-monitor/runs",
        headers=headers,
        params={
            "scenario": "ai_conversation",
            "user_id": 100,
            "limit": 2,
        },
    )

    assert first_response.status_code == 200
    first = api_data(first_response)
    assert first["total"] == 3
    assert [item["actor_username"] for item in first["items"]] == [
        "deleted_user",
        "deleted_user",
    ]
    assert first["next_cursor"]

    second_response = client.get(
        "/api/v1/admin/agent-monitor/runs",
        headers=headers,
        params={
            "scenario": "ai_conversation",
            "user_id": 100,
            "limit": 2,
            "cursor": first["next_cursor"],
        },
    )
    second = api_data(second_response)
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None


@pytest.mark.asyncio
async def test_admin_agent_monitor_detail_returns_ordered_events(
    client: TestClient,
    db_session: AsyncSession,
):
    """运行详情与事件接口必须返回完整且按 sequence 排序的时间线。"""
    admin = await _create_monitor_api_user(
        db_session, "monitor_detail_admin", role=UserRole.SUPER_ADMIN
    )
    run_id = uuid4()
    now = datetime.now(timezone.utc)
    db_session.add(
        AgentRun(
            id=run_id,
            trace_id=run_id,
            scenario="ai_conversation",
            workflow_type="graph",
            workflow_name="conversation",
            actor_user_id=321,
            actor_username="snapshot_user",
            status="FAILED",
            input={"content": "hello"},
            error={"message": "failed"},
            started_at=now,
        )
    )
    db_session.add_all(
        [
            AgentEvent(
                run_id=run_id,
                sequence=2,
                event_type="llm.failed",
                component_type="llm",
                status="FAILED",
                occurred_at=now,
            ),
            AgentEvent(
                run_id=run_id,
                sequence=1,
                event_type="message.received",
                component_type="message",
                status="SUCCEEDED",
                occurred_at=now,
            ),
        ]
    )
    await db_session.commit()
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=admin.id)}"
    }

    detail_response = client.get(
        f"/api/v1/admin/agent-monitor/runs/{run_id}",
        headers=headers,
    )
    events_response = client.get(
        f"/api/v1/admin/agent-monitor/runs/{run_id}/events",
        headers=headers,
    )

    detail = api_data(detail_response)
    events = api_data(events_response)
    assert detail["input"] == {"content": "hello"}
    assert detail["actor_username"] == "snapshot_user"
    assert [event["sequence"] for event in events] == [1, 2]


@pytest.mark.asyncio
async def test_agent_monitor_admin_api_rejects_regular_user(
    client: TestClient,
    db_session: AsyncSession,
):
    """普通用户不得读取 Agent 监控记录。"""
    user = await _create_monitor_api_user(
        db_session, "monitor_regular_user", role=UserRole.USER
    )
    headers = {
        "Authorization": f"Bearer {create_access_token(subject=user.id)}"
    }

    response = client.get(
        "/api/v1/admin/agent-monitor/runs",
        headers=headers,
    )

    assert response.status_code == 403
