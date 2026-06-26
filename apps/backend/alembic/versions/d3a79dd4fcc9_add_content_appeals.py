"""add_content_appeals

Revision ID: d3a79dd4fcc9
Revises: 429aba3b5ccd
Create Date: 2026-06-26 22:22:06.412007

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3a79dd4fcc9"
down_revision: Union[str, Sequence[str], None] = "429aba3b5ccd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_appeals",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("content_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("moderation_version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("appeal_reason", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        "chk_content_appeals_type",
        "content_appeals",
        "content_type IN ('comment', 'space_post', 'playlist', 'user_profile')",
    )
    op.create_check_constraint(
        "chk_content_appeals_status",
        "content_appeals",
        "status IN ('PENDING', 'APPROVED', 'DENIED')",
    )
    op.create_index(
        "uq_content_appeal_pending",
        "content_appeals",
        ["content_type", "content_id", "moderation_version"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "idx_content_appeals_status",
        "content_appeals",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_content_appeals_user",
        "content_appeals",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("content_appeals")
