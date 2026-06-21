"""Agent 运行与事件监控 ORM 模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base


class AgentRun(Base):
    """一次 Graph、Chain 或其它 Agent 工作流运行。"""

    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    trace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    scenario: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_type: Mapped[str] = mapped_column(String(32), nullable=False)
    workflow_name: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_version: Mapped[str | None] = mapped_column(String(64))

    # 运行时快照，不建立 users 外键。用户删除后监控记录必须保留。
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    actor_username: Mapped[str | None] = mapped_column(String(64))
    subject_type: Mapped[str | None] = mapped_column(String(64))
    subject_id: Mapped[str | None] = mapped_column(String(128))
    thread_id: Mapped[str | None] = mapped_column(String(128))

    status: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128))
    input: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB
    )
    output: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB
    )
    error: Mapped[dict | list | str | None] = mapped_column(JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    event_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    tool_call_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    events: Mapped[list["AgentEvent"]] = relationship(
        "AgentEvent",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgentEvent.sequence",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_agent_runs_status",
        ),
        CheckConstraint(
            "event_count >= 0 AND tool_call_count >= 0",
            name="chk_agent_runs_counts_nonnegative",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="chk_agent_runs_duration_nonnegative",
        ),
        Index(
            "idx_agent_runs_scenario_started",
            "scenario",
            desc("started_at"),
            desc("id"),
        ),
        Index(
            "idx_agent_runs_user_started",
            "actor_user_id",
            desc("started_at"),
            desc("id"),
        ),
        Index(
            "idx_agent_runs_status_started",
            "status",
            desc("started_at"),
            desc("id"),
        ),
        Index("idx_agent_runs_trace_id", "trace_id"),
        Index("idx_agent_runs_thread_id", "thread_id"),
    )


class AgentEvent(Base):
    """Agent 运行中的一条有序监控事件。"""

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    component_type: Mapped[str] = mapped_column(String(32), nullable=False)
    component_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str | None] = mapped_column(String(16))
    payload: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB
    )
    error: Mapped[dict | list | str | None] = mapped_column(JSONB)
    framework_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    framework_parent_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True)
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)

    run: Mapped[AgentRun] = relationship("AgentRun", back_populates="events")

    __table_args__ = (
        UniqueConstraint(
            "run_id", "sequence", name="uq_agent_events_run_sequence"
        ),
        CheckConstraint(
            "sequence > 0", name="chk_agent_events_sequence_positive"
        ),
        CheckConstraint(
            "status IS NULL OR status IN "
            "('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_agent_events_status",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="chk_agent_events_duration_nonnegative",
        ),
        Index("idx_agent_events_run_sequence", "run_id", "sequence"),
        Index(
            "idx_agent_events_type_time",
            "event_type",
            desc("occurred_at"),
        ),
    )
