"""add user music likes drop releases

Revision ID: b7c9d2e4f6a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-16 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c9d2e4f6a8"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_music_likes",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("music_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["music_id"], ["musics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "music_id"),
    )
    op.create_index(
        "idx_user_music_likes_user_time",
        "user_music_likes",
        ["user_id", sa.literal_column("created_at DESC")],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO user_music_likes (user_id, music_id, created_at)
            SELECT p.user_id, pm.music_id, MIN(pm.created_at)
            FROM playlist_musics pm
            JOIN playlists p ON p.id = pm.playlist_id
            WHERE p.is_like = true
            GROUP BY p.user_id, pm.music_id
            ON CONFLICT (user_id, music_id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE musics AS m
            SET collect_count = COALESCE(l.like_count, 0)
            FROM (
                SELECT music_id, COUNT(*) AS like_count
                FROM user_music_likes
                GROUP BY music_id
            ) AS l
            WHERE m.id = l.music_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE musics AS m
            SET collect_count = 0
            WHERE NOT EXISTS (
                SELECT 1
                FROM user_music_likes AS l
                WHERE l.music_id = m.id
            )
            """
        )
    )

    op.drop_table("user_music_releases")


def downgrade() -> None:
    op.create_table(
        "user_music_releases",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("music_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["music_id"], ["musics.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "music_id"),
    )
    op.create_index(
        "idx_user_music_releases_user_time",
        "user_music_releases",
        ["user_id", sa.literal_column("created_at DESC")],
    )
    op.drop_index("idx_user_music_likes_user_time", table_name="user_music_likes")
    op.drop_table("user_music_likes")
