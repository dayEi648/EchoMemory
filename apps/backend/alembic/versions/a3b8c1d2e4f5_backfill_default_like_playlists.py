"""backfill default like playlists

Revision ID: a3b8c1d2e4f5
Revises: f2a1c9d4e8b6
Create Date: 2026-06-11 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3b8c1d2e4f5"
down_revision: Union[str, Sequence[str], None] = "6d7bd218983c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为缺少系统喜欢歌单的已有用户补建默认歌单。"""
    op.execute(
        """
        INSERT INTO playlists (
            title,
            user_id,
            is_private,
            is_like,
            collect_count,
            play_count,
            hot,
            comment_count,
            is_recommended,
            created_at,
            updated_at
        )
        SELECT
            '我喜欢的音乐',
            u.id,
            TRUE,
            TRUE,
            0,
            0,
            0,
            0,
            FALSE,
            NOW(),
            NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1
            FROM playlists p
            WHERE p.user_id = u.id
              AND p.is_like = TRUE
        )
        """
    )


def downgrade() -> None:
    """移除迁移补建的系统喜欢歌单（仅删除无歌曲的默认歌单）。"""
    op.execute(
        """
        DELETE FROM playlists p
        WHERE p.is_like = TRUE
          AND p.title = '我喜欢的音乐'
          AND NOT EXISTS (
              SELECT 1
              FROM playlist_musics pm
              WHERE pm.playlist_id = p.id
          )
        """
    )
