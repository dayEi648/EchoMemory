"""Agent 监控管理查询服务。"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import desc, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.models.agent_monitor import AgentEvent, AgentRun
from echomemory_backend.schemas.agent_monitor import (
    AgentEventOut,
    AgentRunDetailOut,
    AgentRunListParams,
    AgentRunOut,
    AgentScenarioOut,
)


def _encode_cursor(started_at: datetime, run_id: UUID) -> str:
    """编码不透明的 `(started_at, id)` 游标。"""
    raw = json.dumps(
        {"started_at": started_at.isoformat(), "id": str(run_id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """解码列表游标，无效游标按请求错误处理。"""
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(cursor + padding).decode("utf-8")
        )
        started_at = datetime.fromisoformat(payload["started_at"])
        if started_at.tzinfo is None:
            raise ValueError("cursor timestamp must include timezone")
        return started_at, UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BusinessError(
            "无效的分页游标",
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        ) from exc


def _run_out(run: AgentRun) -> AgentRunOut:
    """把 ORM 运行记录转换为列表输出。"""
    return AgentRunOut(
        id=run.id,
        trace_id=run.trace_id,
        parent_run_id=run.parent_run_id,
        scenario=run.scenario,
        workflow_type=run.workflow_type,
        workflow_name=run.workflow_name,
        workflow_version=run.workflow_version,
        actor_user_id=run.actor_user_id,
        actor_username=run.actor_username,
        subject_type=run.subject_type,
        subject_id=run.subject_id,
        thread_id=run.thread_id,
        status=run.status,
        model=run.model,
        prompt_tokens=run.prompt_tokens,
        completion_tokens=run.completion_tokens,
        total_tokens=run.total_tokens,
        event_count=run.event_count,
        tool_call_count=run.tool_call_count,
        started_at=run.started_at,
        ended_at=run.ended_at,
        duration_ms=run.duration_ms,
    )


def _build_filters(params: AgentRunListParams) -> list:
    """构造运行列表公共筛选条件。"""
    filters: list = []
    if params.scenario:
        filters.append(AgentRun.scenario == params.scenario)
    if params.user_id is not None:
        filters.append(AgentRun.actor_user_id == params.user_id)
    if params.status:
        filters.append(AgentRun.status == params.status.upper())
    if params.model:
        filters.append(AgentRun.model == params.model)
    if params.start_time:
        filters.append(AgentRun.started_at >= params.start_time)
    if params.end_time:
        filters.append(AgentRun.started_at <= params.end_time)
    if params.q:
        escaped = (
            params.q.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped}%"
        filters.append(
            or_(
                AgentRun.actor_username.ilike(pattern, escape="\\"),
                AgentRun.workflow_name.ilike(pattern, escape="\\"),
                AgentRun.subject_id.ilike(pattern, escape="\\"),
                AgentRun.thread_id.ilike(pattern, escape="\\"),
                AgentRun.model.ilike(pattern, escape="\\"),
            )
        )
    return filters


async def list_runs(
    db: AsyncSession,
    params: AgentRunListParams,
) -> tuple[list[AgentRunOut], int, str | None]:
    """按筛选条件使用 keyset cursor 分页查询运行。"""
    if (
        params.start_time is not None
        and params.end_time is not None
        and params.start_time > params.end_time
    ):
        raise BusinessError(
            "起始时间不能晚于结束时间",
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        )
    filters = _build_filters(params)
    total = (
        await db.execute(
            select(func.count()).select_from(AgentRun).where(*filters)
        )
    ).scalar_one()

    page_filters = list(filters)
    if params.cursor:
        started_at, run_id = _decode_cursor(params.cursor)
        page_filters.append(
            tuple_(AgentRun.started_at, AgentRun.id)
            < tuple_(started_at, run_id)
        )

    rows = list(
        (
            await db.execute(
                select(AgentRun)
                .where(*page_filters)
                .order_by(desc(AgentRun.started_at), desc(AgentRun.id))
                .limit(params.limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(rows) > params.limit
    page_rows = rows[: params.limit]
    next_cursor = None
    if has_more and page_rows:
        last = page_rows[-1]
        next_cursor = _encode_cursor(last.started_at, last.id)
    return [_run_out(run) for run in page_rows], total, next_cursor


async def get_run(db: AsyncSession, run_id: UUID) -> AgentRunDetailOut:
    """获取单条 Agent 运行详情。"""
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise BusinessError(
            "Agent 运行记录不存在", code=ErrorCode.RESOURCE_NOT_FOUND
        )
    return AgentRunDetailOut(
        **_run_out(run).model_dump(),
        input=run.input,
        output=run.output,
        error=run.error,
        metadata=run.metadata_,
    )


async def list_events(
    db: AsyncSession, run_id: UUID
) -> list[AgentEventOut]:
    """按 sequence 返回指定运行的完整时间线。"""
    exists = await db.scalar(
        select(AgentRun.id).where(AgentRun.id == run_id)
    )
    if exists is None:
        raise BusinessError(
            "Agent 运行记录不存在", code=ErrorCode.RESOURCE_NOT_FOUND
        )
    events = list(
        (
            await db.execute(
                select(AgentEvent)
                .where(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    return [
        AgentEventOut(
            id=event.id,
            run_id=event.run_id,
            sequence=event.sequence,
            event_type=event.event_type,
            component_type=event.component_type,
            component_name=event.component_name,
            status=event.status,
            payload=event.payload,
            error=event.error,
            framework_run_id=event.framework_run_id,
            framework_parent_run_id=event.framework_parent_run_id,
            occurred_at=event.occurred_at,
            ended_at=event.ended_at,
            duration_ms=event.duration_ms,
        )
        for event in events
    ]


async def list_scenarios(db: AsyncSession) -> list[AgentScenarioOut]:
    """列出已有监控场景及运行数量。"""
    rows = (
        await db.execute(
            select(
                AgentRun.scenario,
                func.count(AgentRun.id),
                func.max(AgentRun.started_at),
            )
            .group_by(AgentRun.scenario)
            .order_by(AgentRun.scenario)
        )
    ).all()
    return [
        AgentScenarioOut(
            scenario=scenario,
            run_count=run_count,
            latest_started_at=latest_started_at,
        )
        for scenario, run_count, latest_started_at in rows
    ]
