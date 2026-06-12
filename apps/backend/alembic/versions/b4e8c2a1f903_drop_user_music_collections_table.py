"""drop_user_music_collections_table

Revision ID: b4e8c2a1f903
Revises: fdaf05e679b3
Create Date: 2026-06-12 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4e8c2a1f903"
down_revision: Union[str, Sequence[str], None] = "fdaf05e679b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除已废弃的 user_music_collections 表（歌曲收藏已改为歌单派生）。"""
    op.drop_index(
        "idx_user_music_collections_user_time", table_name="user_music_collections"
    )
    op.drop_table("user_music_collections")


def downgrade() -> None:
    """恢复 user_music_collections 表。"""
    op.create_table(
        "user_music_collections",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("music_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["music_id"], ["musics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "music_id"),
    )
    op.create_index(
        "idx_user_music_collections_user_time",
        "user_music_collections",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
