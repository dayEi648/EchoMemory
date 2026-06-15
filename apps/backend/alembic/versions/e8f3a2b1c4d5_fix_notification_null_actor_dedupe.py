"""fix_notification_null_actor_dedupe

Revision ID: e8f3a2b1c4d5
Revises: 735845797c23
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e8f3a2b1c4d5"
down_revision: Union[str, Sequence[str], None] = "735845797c23"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将通知去重索引拆分为 actor 非空与系统通知（actor_id IS NULL）两条部分唯一索引。"""
    # 清理历史重复未读系统通知，保留每组中 id 最小的一条
    op.execute(
        sa.text(
            """
            DELETE FROM notifications
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY recipient_id, type, target_type, target_id
                               ORDER BY id
                           ) AS rn
                    FROM notifications
                    WHERE is_read = false AND actor_id IS NULL
                ) duplicates
                WHERE duplicates.rn > 1
            )
            """
        )
    )

    op.drop_index(
        "uq_notifications_dedupe_unread",
        table_name="notifications",
        postgresql_where=sa.text("is_read = false"),
    )
    op.create_index(
        "uq_notifications_dedupe_unread_with_actor",
        "notifications",
        ["recipient_id", "actor_id", "type", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("is_read = false AND actor_id IS NOT NULL"),
    )
    op.create_index(
        "uq_notifications_dedupe_unread_system",
        "notifications",
        ["recipient_id", "type", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("is_read = false AND actor_id IS NULL"),
    )


def downgrade() -> None:
    """恢复为单条包含 actor_id 的去重索引。"""
    op.drop_index(
        "uq_notifications_dedupe_unread_system",
        table_name="notifications",
        postgresql_where=sa.text("is_read = false AND actor_id IS NULL"),
    )
    op.drop_index(
        "uq_notifications_dedupe_unread_with_actor",
        table_name="notifications",
        postgresql_where=sa.text("is_read = false AND actor_id IS NOT NULL"),
    )
    op.create_index(
        "uq_notifications_dedupe_unread",
        "notifications",
        ["recipient_id", "actor_id", "type", "target_type", "target_id"],
        unique=True,
        postgresql_where=sa.text("is_read = false"),
    )
