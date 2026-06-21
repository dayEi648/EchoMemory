"""add Agent monitoring tables

Revision ID: 6f4c2a8d1b90
Revises: e4b7a91c2d6f
Create Date: 2026-06-21 14:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "6f4c2a8d1b90"
down_revision: Union[str, Sequence[str], None] = "e4b7a91c2d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建通用 Agent 运行与事件表。"""
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scenario", sa.String(length=64), nullable=False),
        sa.Column("workflow_type", sa.String(length=32), nullable=False),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("workflow_version", sa.String(length=64), nullable=True),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("subject_type", sa.String(length=64), nullable=True),
        sa.Column("subject_id", sa.String(length=128), nullable=True),
        sa.Column("thread_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("event_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tool_call_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_agent_runs_status",
        ),
        sa.CheckConstraint(
            "event_count >= 0 AND tool_call_count >= 0",
            name="chk_agent_runs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="chk_agent_runs_duration_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"], ["agent_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_agent_runs_scenario_started",
        "agent_runs",
        ["scenario", sa.text("started_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "idx_agent_runs_user_started",
        "agent_runs",
        ["actor_user_id", sa.text("started_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "idx_agent_runs_status_started",
        "agent_runs",
        ["status", sa.text("started_at DESC"), sa.text("id DESC")],
    )
    op.create_index("idx_agent_runs_trace_id", "agent_runs", ["trace_id"])
    op.create_index("idx_agent_runs_thread_id", "agent_runs", ["thread_id"])

    op.create_table(
        "agent_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("component_type", sa.String(length=32), nullable=False),
        sa.Column("component_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("framework_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "framework_parent_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "sequence > 0", name="chk_agent_events_sequence_positive"
        ),
        sa.CheckConstraint(
            "status IS NULL OR status IN "
            "('RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_agent_events_status",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="chk_agent_events_duration_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_agent_events_run_sequence"
        ),
    )
    op.create_index(
        "idx_agent_events_run_sequence",
        "agent_events",
        ["run_id", "sequence"],
    )
    op.create_index(
        "idx_agent_events_type_time",
        "agent_events",
        ["event_type", sa.text("occurred_at DESC")],
    )


def downgrade() -> None:
    """删除 Agent 监控表。"""
    op.drop_index("idx_agent_events_type_time", table_name="agent_events")
    op.drop_index("idx_agent_events_run_sequence", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("idx_agent_runs_thread_id", table_name="agent_runs")
    op.drop_index("idx_agent_runs_trace_id", table_name="agent_runs")
    op.drop_index("idx_agent_runs_status_started", table_name="agent_runs")
    op.drop_index("idx_agent_runs_user_started", table_name="agent_runs")
    op.drop_index("idx_agent_runs_scenario_started", table_name="agent_runs")
    op.drop_table("agent_runs")

