"""extend_moderation_to_playlists_and_users

Revision ID: 037245d380e7
Revises: 4c8e1f6a2b9d
Create Date: 2026-06-26 21:19:27.458300

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "037245d380e7"
down_revision: Union[str, Sequence[str], None] = "4c8e1f6a2b9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MODERATION_COLUMNS = [
    ("safety_score", sa.Integer()),
    ("recommendation_score", sa.Integer()),
    ("safety_level", sa.String(16)),
    ("recommendation_level", sa.String(16)),
    ("moderation_status", sa.String(16)),
    ("moderation_reason", sa.Text()),
    ("moderated_at", sa.DateTime(timezone=True)),
    ("moderation_version", sa.Integer(), 1),
    ("deletion_reason", sa.String(32)),
]


def _add_moderation_columns(table: str, prefix: str = "") -> None:
    for col_name, col_type, *default in _MODERATION_COLUMNS:
        full_name = f"{prefix}{col_name}"
        kwargs: dict = {"nullable": True}
        if default:
            kwargs["server_default"] = sa.text(str(default[0]))
        op.add_column(table, sa.Column(full_name, col_type, **kwargs))


def _drop_moderation_columns(table: str, prefix: str = "") -> None:
    for col_name, *_ in _MODERATION_COLUMNS:
        op.drop_column(table, f"{prefix}{col_name}")


def _alter_content_type_check(
    table: str,
    constraint: str,
    old_values: str,
    new_values: str,
) -> None:
    op.execute(
        f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}"
    )
    op.execute(
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
        f"CHECK (content_type IN ({new_values})) NOT VALID"
    )


_NEW_TYPES = "'comment', 'space_post', 'playlist', 'user_profile'"
_OLD_TYPES = "'comment', 'space_post'"


def upgrade() -> None:
    # 1. 给 playlists 添加审核列
    _add_moderation_columns("playlists")

    # 2. 给 users 添加个人资料审核列（前缀 profile_，避免与现有 safety_score 冲突）
    _add_moderation_columns("users", prefix="profile_")

    # 3. 扩展 content_moderation_tasks 的 content_type 约束
    _alter_content_type_check(
        "content_moderation_tasks",
        "chk_content_moderation_tasks_type",
        _OLD_TYPES,
        _NEW_TYPES,
    )

    # 4. 扩展 content_moderation_history 的 content_type 约束
    _alter_content_type_check(
        "content_moderation_history",
        "chk_content_moderation_history_type",
        _OLD_TYPES,
        _NEW_TYPES,
    )


def downgrade() -> None:
    # 回退约束
    _alter_content_type_check(
        "content_moderation_history",
        "chk_content_moderation_history_type",
        _NEW_TYPES,
        _OLD_TYPES,
    )
    _alter_content_type_check(
        "content_moderation_tasks",
        "chk_content_moderation_tasks_type",
        _NEW_TYPES,
        _OLD_TYPES,
    )
    _drop_moderation_columns("users", prefix="profile_")
    _drop_moderation_columns("playlists")
