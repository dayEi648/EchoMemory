"""Agent 监控管理 API，仅供管理员访问。"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.schemas.agent_monitor import (
    AgentEventOut,
    AgentRunDetailOut,
    AgentRunListParams,
    AgentScenarioOut,
    PaginatedAgentRunsOut,
)
from echomemory_backend.services import agent_monitor_service

router = APIRouter(
    prefix="/admin/agent-monitor", tags=["admin-agent-monitor"]
)


@router.get("/scenarios", response_model=list[AgentScenarioOut])
async def admin_list_agent_scenarios(
    db: SessionDep,
    _: AdminUser,
) -> list[AgentScenarioOut]:
    """列出已有 Agent 监控场景。"""
    return await agent_monitor_service.list_scenarios(db)


@router.get("/runs", response_model=PaginatedAgentRunsOut)
async def admin_list_agent_runs(
    db: SessionDep,
    _: AdminUser,
    scenario: str | None = Query(None, max_length=64),
    user_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=16),
    model: str | None = Query(None, max_length=128),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    q: str | None = Query(None, max_length=200),
    cursor: str | None = Query(None, max_length=500),
    limit: int = Query(20, ge=1, le=100),
) -> PaginatedAgentRunsOut:
    """筛选并游标分页查询 Agent 运行。"""
    params = AgentRunListParams(
        scenario=scenario,
        user_id=user_id,
        status=status,
        model=model,
        start_time=start_time,
        end_time=end_time,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    items, total, next_cursor = await agent_monitor_service.list_runs(
        db, params
    )
    return PaginatedAgentRunsOut(
        items=items, total=total, next_cursor=next_cursor
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailOut)
async def admin_get_agent_run(
    db: SessionDep,
    _: AdminUser,
    run_id: UUID,
) -> AgentRunDetailOut:
    """获取 Agent 运行详情。"""
    return await agent_monitor_service.get_run(db, run_id)


@router.get("/runs/{run_id}/events", response_model=list[AgentEventOut])
async def admin_list_agent_events(
    db: SessionDep,
    _: AdminUser,
    run_id: UUID,
) -> list[AgentEventOut]:
    """获取 Agent 运行事件时间线。"""
    return await agent_monitor_service.list_events(db, run_id)

