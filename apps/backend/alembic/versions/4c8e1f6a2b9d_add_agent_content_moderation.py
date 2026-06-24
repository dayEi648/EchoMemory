"""add Agent content moderation

Revision ID: 4c8e1f6a2b9d
Revises: 6f4c2a8d1b90
Create Date: 2026-06-21 18:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "4c8e1f6a2b9d"
down_revision: Union[str, Sequence[str], None] = "6f4c2a8d1b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_content_columns(table_name: str) -> None:
    """为评论或空间动态增加统一审核字段。"""
    op.add_column(
        table_name,
        sa.Column(
            "recommendation_score",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        table_name, sa.Column("safety_level", sa.String(16), nullable=True)
    )
    op.add_column(
        table_name,
        sa.Column("recommendation_level", sa.String(16), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column(
            "moderation_status",
            sa.String(16),
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column(
        table_name, sa.Column("moderation_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        table_name,
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        table_name,
        sa.Column(
            "moderation_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        table_name,
        sa.Column("deletion_reason", sa.String(32), nullable=True),
    )
    op.create_check_constraint(
        f"chk_{table_name}_recommendation_score",
        table_name,
        "recommendation_score BETWEEN 0 AND 10",
    )
    op.create_check_constraint(
        f"chk_{table_name}_safety_level",
        table_name,
        "safety_level IS NULL OR safety_level IN ('SAFE', 'RISKY', 'DANGEROUS')",
    )
    op.create_check_constraint(
        f"chk_{table_name}_recommendation_level",
        table_name,
        "recommendation_level IS NULL OR recommendation_level IN ('NORMAL', 'RECOMMENDED')",
    )
    op.create_check_constraint(
        f"chk_{table_name}_moderation_status",
        table_name,
        "moderation_status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'MANUAL')",
    )
    op.create_check_constraint(
        f"chk_{table_name}_moderation_version",
        table_name,
        "moderation_version > 0",
    )
    op.create_index(
        f"idx_{table_name}_moderation_admin",
        table_name,
        ["moderation_status", "is_deleted", sa.text("created_at DESC")],
    )


def upgrade() -> None:
    """创建审核字段、任务、历史和统计表。"""
    _add_content_columns("comments")
    _add_content_columns("space_posts")
    op.add_column(
        "space_posts",
        sa.Column(
            "safety",
            sa.SmallInteger(),
            server_default="10",
            nullable=False,
        ),
    )
    op.add_column(
        "space_posts",
        sa.Column(
            "is_recommended",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "chk_space_posts_safety",
        "space_posts",
        "safety BETWEEN 0 AND 10",
    )

    op.create_table(
        "content_moderation_tasks",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("moderation_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "attempt_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "max_attempts", sa.Integer(), server_default="3", nullable=False
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "agent_run_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('comment', 'space_post')",
            name="chk_content_moderation_tasks_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'CANCELLED')",
            name="chk_content_moderation_tasks_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
            name="chk_content_moderation_tasks_attempts",
        ),
        sa.CheckConstraint(
            "moderation_version > 0",
            name="chk_content_moderation_tasks_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "content_type",
            "content_id",
            "moderation_version",
            name="uq_content_moderation_task_version",
        ),
    )
    op.create_index(
        "idx_content_moderation_tasks_claim",
        "content_moderation_tasks",
        ["status", "available_at", "id"],
    )
    op.create_index(
        "idx_content_moderation_tasks_content",
        "content_moderation_tasks",
        ["content_type", "content_id"],
    )

    op.create_table(
        "content_moderation_history",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("moderation_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("safety_score", sa.Integer(), nullable=False),
        sa.Column("recommendation_score", sa.Integer(), nullable=False),
        sa.Column("safety_level", sa.String(16), nullable=False),
        sa.Column("recommendation_level", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "agent_run_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_type IN ('comment', 'space_post')",
            name="chk_content_moderation_history_type",
        ),
        sa.CheckConstraint(
            "source IN ('AGENT', 'MANUAL')",
            name="chk_content_moderation_history_source",
        ),
        sa.CheckConstraint(
            "safety_score BETWEEN 0 AND 10 AND recommendation_score BETWEEN 0 AND 10",
            name="chk_content_moderation_history_scores",
        ),
        sa.CheckConstraint(
            "safety_level IN ('SAFE', 'RISKY', 'DANGEROUS')",
            name="chk_content_moderation_history_safety_level",
        ),
        sa.CheckConstraint(
            "recommendation_level IN ('NORMAL', 'RECOMMENDED')",
            name="chk_content_moderation_history_recommendation_level",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_content_moderation_history_content",
        "content_moderation_history",
        ["content_type", "content_id", "created_at"],
    )
    op.create_index(
        "idx_content_moderation_history_user",
        "content_moderation_history",
        ["user_id", "created_at"],
    )

    op.create_table(
        "user_content_moderation_stats",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "risky_count", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column(
            "dangerous_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "recommended_count",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risky_count >= 0 AND dangerous_count >= 0 AND recommended_count >= 0",
            name="chk_user_content_moderation_stats_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.drop_constraint(
        "chk_notifications_type", "notifications", type_="check"
    )
    op.create_check_constraint(
        "chk_notifications_type",
        "notifications",
        "type >= 0 AND type <= 5",
    )

    op.execute(
        """
        INSERT INTO content_moderation_tasks
            (content_type, content_id, moderation_version)
        SELECT 'comment', id, moderation_version
        FROM comments
        WHERE is_deleted = false
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO content_moderation_tasks
            (content_type, content_id, moderation_version)
        SELECT 'space_post', id, moderation_version
        FROM space_posts
        WHERE is_deleted = false
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """删除内容审核结构。"""
    op.drop_constraint(
        "chk_notifications_type", "notifications", type_="check"
    )
    op.create_check_constraint(
        "chk_notifications_type",
        "notifications",
        "type >= 0 AND type <= 4",
    )
    op.drop_table("user_content_moderation_stats")
    op.drop_index(
        "idx_content_moderation_history_user",
        table_name="content_moderation_history",
    )
    op.drop_index(
        "idx_content_moderation_history_content",
        table_name="content_moderation_history",
    )
    op.drop_table("content_moderation_history")
    op.drop_index(
        "idx_content_moderation_tasks_content",
        table_name="content_moderation_tasks",
    )
    op.drop_index(
        "idx_content_moderation_tasks_claim",
        table_name="content_moderation_tasks",
    )
    op.drop_table("content_moderation_tasks")

    op.drop_constraint(
        "chk_space_posts_safety", "space_posts", type_="check"
    )
    op.drop_column("space_posts", "is_recommended")
    op.drop_column("space_posts", "safety")
    for table_name in ("space_posts", "comments"):
        op.drop_index(
            f"idx_{table_name}_moderation_admin", table_name=table_name
        )
        for suffix in (
            "moderation_version",
            "moderation_status",
            "recommendation_level",
            "safety_level",
            "recommendation_score",
        ):
            op.drop_constraint(
                f"chk_{table_name}_{suffix}",
                table_name,
                type_="check",
            )
        op.drop_column(table_name, "deletion_reason")
        op.drop_column(table_name, "moderation_version")
        op.drop_column(table_name, "moderated_at")
        op.drop_column(table_name, "moderation_reason")
        op.drop_column(table_name, "moderation_status")
        op.drop_column(table_name, "recommendation_level")
        op.drop_column(table_name, "safety_level")
        op.drop_column(table_name, "recommendation_score")
