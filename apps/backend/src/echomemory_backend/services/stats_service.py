"""管理仪表盘统计服务。"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.album import Album
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User


async def get_dashboard_stats(db: AsyncSession) -> dict[str, int]:
    """聚合统计：用户 / 音乐 / 专辑 / 歌单 / 评论 / 动态总数。"""
    user_count = (
        await db.execute(
            select(func.count()).where(
                User.is_deleted == False,
            )
        )
    ).scalar_one()

    music_count = (
        await db.execute(
            select(func.count()).where(
                Music.is_published == True,
            )
        )
    ).scalar_one()

    album_count = (
        await db.execute(
            select(func.count()).where(
                Album.is_deleted == False,
            )
        )
    ).scalar_one()

    playlist_count = (
        await db.execute(select(func.count()).select_from(Playlist))
    ).scalar_one()

    comment_count = (
        await db.execute(
            select(func.count()).where(
                Comment.is_deleted == False,
            )
        )
    ).scalar_one()

    space_post_count = (
        await db.execute(
            select(func.count()).where(
                SpacePost.is_deleted == False,
            )
        )
    ).scalar_one()

    return {
        "users": int(user_count),
        "music": int(music_count),
        "albums": int(album_count),
        "playlists": int(playlist_count),
        "comments": int(comment_count),
        "space_posts": int(space_post_count),
    }
