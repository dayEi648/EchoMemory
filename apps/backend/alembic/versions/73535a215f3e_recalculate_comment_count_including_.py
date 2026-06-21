"""recalculate comment count including replies

Revision ID: 73535a215f3e
Revises: 9fd0a5c411bb
Create Date: 2026-06-20 18:12:42.841690

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '73535a215f3e'
down_revision: Union[str, Sequence[str], None] = '9fd0a5c411bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """重新计算 music / playlist / space_post 的 comment_count，包含根评论及其下所有可见回复。"""
    # 可见评论定义：is_deleted = FALSE 且（本身是根评论 OR 所属根评论未删除）
    op.execute(
        """
        UPDATE musics m
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.music_id = m.id
              AND c.is_deleted = FALSE
              AND (
                  c.root_id IS NULL
                  OR NOT EXISTS (
                      SELECT 1 FROM comments r WHERE r.id = c.root_id AND r.is_deleted = TRUE
                  )
              )
        )
        """
    )
    op.execute(
        """
        UPDATE playlists p
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.playlist_id = p.id
              AND c.is_deleted = FALSE
              AND (
                  c.root_id IS NULL
                  OR NOT EXISTS (
                      SELECT 1 FROM comments r WHERE r.id = c.root_id AND r.is_deleted = TRUE
                  )
              )
        )
        """
    )
    op.execute(
        """
        UPDATE space_posts sp
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.space_post_id = sp.id
              AND c.is_deleted = FALSE
              AND (
                  c.root_id IS NULL
                  OR NOT EXISTS (
                      SELECT 1 FROM comments r WHERE r.id = c.root_id AND r.is_deleted = TRUE
                  )
              )
        )
        """
    )


def downgrade() -> None:
    """回退为仅统计根评论数（与旧业务逻辑一致）。"""
    op.execute(
        """
        UPDATE musics m
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.music_id = m.id
              AND c.is_deleted = FALSE
              AND c.parent_id IS NULL
        )
        """
    )
    op.execute(
        """
        UPDATE playlists p
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.playlist_id = p.id
              AND c.is_deleted = FALSE
              AND c.parent_id IS NULL
        )
        """
    )
    op.execute(
        """
        UPDATE space_posts sp
        SET comment_count = (
            SELECT COUNT(*)
            FROM comments c
            WHERE c.space_post_id = sp.id
              AND c.is_deleted = FALSE
              AND c.parent_id IS NULL
        )
        """
    )
