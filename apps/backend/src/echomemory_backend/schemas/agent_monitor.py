"""Agent 监控管理 API Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunListParams(BaseModel):
    """Agent 运行列表筛选参数。"""

    scenario: str | None = None
    user_id: int | None = Field(None, ge=1)
    status: str | None = None
    model: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    q: str | None = Field(None, max_length=200)
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)


class AgentRunOut(BaseModel):
    """Agent 运行列表项。"""

    id: UUID
    trace_id: UUID
    parent_run_id: UUID | None = None
    scenario: str
    workflow_type: str
    workflow_name: str
    workflow_version: str | None = None
    actor_user_id: int | None = None
    actor_username: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    thread_id: str | None = None
    status: str
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    event_count: int
    tool_call_count: int
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None


class AgentRunDetailOut(AgentRunOut):
    """Agent 运行详情。"""

    input: Any = None
    output: Any = None
    error: Any = None
    metadata: dict[str, Any] | None = None


class PaginatedAgentRunsOut(BaseModel):
    """Agent 运行游标分页结果。"""

    items: list[AgentRunOut]
    total: int
    next_cursor: str | None = None


class AgentEventOut(BaseModel):
    """Agent 运行事件。"""

    id: int
    run_id: UUID
    sequence: int
    event_type: str
    component_type: str
    component_name: str | None = None
    status: str | None = None
    payload: Any = None
    error: Any = None
    framework_run_id: UUID | None = None
    framework_parent_run_id: UUID | None = None
    occurred_at: datetime
    ended_at: datetime | None = None
    duration_ms: int | None = None


class AgentScenarioOut(BaseModel):
    """已产生监控记录的 Agent 场景。"""

    scenario: str
    run_count: int
    latest_started_at: datetime

