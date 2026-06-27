"""管理仪表盘统计服务。"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.agent_monitor import AgentRun
from echomemory_backend.models.album import Album
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.content_moderation import ContentModerationTask
from echomemory_backend.models.dictionary import Style
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User

_USER_STATUS_LABELS = {0: "正常", 1: "禁言", 2: "限制", 3: "封禁"}
_USER_ROLE_LABELS = {0: "普通用户", 1: "VIP", 2: "管理员", 3: "超级管理员"}


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """聚合管理仪表盘所需的全部统计数据。"""
    since = func.now() - timedelta(days=30)
    since_24h = func.now() - timedelta(hours=24)

    # ------------------------------------------------------------------
    # 1. 核心总量
    # ------------------------------------------------------------------
    user_count = (
        await db.execute(select(func.count()).where(User.is_deleted == False))
    ).scalar_one()

    music_count = (
        await db.execute(select(func.count()).where(Music.is_published == True))
    ).scalar_one()

    album_count = (
        await db.execute(select(func.count()).where(Album.is_deleted == False))
    ).scalar_one()

    playlist_count = (await db.execute(select(func.count()).select_from(Playlist))).scalar_one()

    comment_count = (
        await db.execute(select(func.count()).where(Comment.is_deleted == False))
    ).scalar_one()

    space_post_count = (
        await db.execute(select(func.count()).where(SpacePost.is_deleted == False))
    ).scalar_one()

    # ------------------------------------------------------------------
    # 2. 用户分布
    # ------------------------------------------------------------------
    status_rows = (
        await db.execute(
            select(User.status, func.count())
            .where(User.is_deleted == False)
            .group_by(User.status)
            .order_by(User.status)
        )
    ).all()
    user_status_distribution = [
        {
            "key": str(status),
            "label": _USER_STATUS_LABELS.get(int(status), "未知"),
            "count": int(count),
        }
        for status, count in status_rows
    ]

    role_rows = (
        await db.execute(
            select(User.role, func.count())
            .where(User.is_deleted == False)
            .group_by(User.role)
            .order_by(User.role)
        )
    ).all()
    user_role_distribution = [
        {
            "key": str(role),
            "label": _USER_ROLE_LABELS.get(int(role), "未知"),
            "count": int(count),
        }
        for role, count in role_rows
    ]

    # ------------------------------------------------------------------
    # 3. 近 30 天内容增长趋势
    # ------------------------------------------------------------------
    async def _daily_counts(date_col, *filters):
        day_expr = func.date_trunc("day", date_col).label("day")
        rows = await db.execute(
            select(day_expr, func.count().label("cnt"))
            .where(*filters, date_col >= since)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        return {str(row.day.date()): int(row.cnt) for row in rows.all()}

    users_by_day = await _daily_counts(User.created_at, User.is_deleted == False)
    music_by_day = await _daily_counts(Music.created_at, Music.is_published == True)
    comments_by_day = await _daily_counts(Comment.created_at, Comment.is_deleted == False)
    space_posts_by_day = await _daily_counts(
        SpacePost.created_at, SpacePost.is_deleted == False
    )

    today = date.today()
    content_trend = [
        {
            "date": (today - timedelta(days=i)).isoformat(),
            "users": users_by_day.get((today - timedelta(days=i)).isoformat(), 0),
            "music": music_by_day.get((today - timedelta(days=i)).isoformat(), 0),
            "comments": comments_by_day.get((today - timedelta(days=i)).isoformat(), 0),
            "space_posts": space_posts_by_day.get((today - timedelta(days=i)).isoformat(), 0),
        }
        for i in range(29, -1, -1)
    ]

    # ------------------------------------------------------------------
    # 4. 音乐风格分布
    # ------------------------------------------------------------------
    style_rows = (
        await db.execute(
            select(Style.name, func.count(Music.id))
            .join(Music, Music.style_id == Style.id)
            .where(Music.is_published == True)
            .group_by(Style.name)
            .order_by(func.count(Music.id).desc())
        )
    ).all()
    music_style_distribution = [
        {"key": name, "label": name, "count": int(count)}
        for name, count in style_rows
    ]

    # ------------------------------------------------------------------
    # 5. 待审核队列
    # ------------------------------------------------------------------
    pending_comments = (
        await db.execute(
            select(func.count()).where(
                Comment.is_deleted == False,
                Comment.moderation_status == "PENDING",
            )
        )
    ).scalar_one()

    pending_space_posts = (
        await db.execute(
            select(func.count()).where(
                SpacePost.is_deleted == False,
                SpacePost.moderation_status == "PENDING",
            )
        )
    ).scalar_one()

    pending_moderation_tasks = (
        await db.execute(
            select(func.count()).where(ContentModerationTask.status == "PENDING")
        )
    ).scalar_one()

    # ------------------------------------------------------------------
    # 6. 全站互动总量
    # ------------------------------------------------------------------
    total_plays = (
        await db.execute(select(func.coalesce(func.sum(Music.play_count), 0)))
    ).scalar_one()

    async def _sum_column(model, column):
        return (
            await db.execute(select(func.coalesce(func.sum(column), 0)))
        ).scalar_one()

    total_collections = (
        await _sum_column(Music, Music.collect_count)
        + await _sum_column(Album, Album.collect_count)
        + await _sum_column(Playlist, Playlist.collect_count)
    )

    total_forwards = (
        await _sum_column(Music, Music.forward_count)
        + await _sum_column(Album, Album.forward_count)
        + await _sum_column(Playlist, Playlist.forward_count)
        + await _sum_column(SpacePost, SpacePost.forward_count)
    )

    # ------------------------------------------------------------------
    # 7. 热度最高音乐 TOP5
    # ------------------------------------------------------------------
    top_music_rows = (
        await db.execute(
            select(
                Music.id,
                Music.title,
                Music.hot,
                Music.play_count,
                func.string_agg(User.nickname, ", ").label("authors"),
            )
            .join(MusicAuthor, MusicAuthor.music_id == Music.id)
            .join(User, User.id == MusicAuthor.author_id)
            .where(Music.is_published == True)
            .group_by(Music.id, Music.title, Music.hot, Music.play_count)
            .order_by(Music.hot.desc(), Music.play_count.desc())
            .limit(5)
        )
    ).all()
    top_hot_music = [
        {
            "id": int(mid),
            "title": title,
            "authors": authors or "未知",
            "hot": int(hot),
            "play_count": int(play_count),
        }
        for mid, title, hot, play_count, authors in top_music_rows
    ]

    # ------------------------------------------------------------------
    # 8. 最近 24 小时 Agent 运行汇总
    # ------------------------------------------------------------------
    agent_total = (
        await db.execute(
            select(func.count()).where(AgentRun.started_at >= since_24h)
        )
    ).scalar_one()

    agent_succeeded = (
        await db.execute(
            select(func.count()).where(
                AgentRun.started_at >= since_24h,
                AgentRun.status == "SUCCEEDED",
            )
        )
    ).scalar_one()

    agent_failed = (
        await db.execute(
            select(func.count()).where(
                AgentRun.started_at >= since_24h,
                AgentRun.status == "FAILED",
            )
        )
    ).scalar_one()

    total_tokens_24h = (
        await db.execute(
            select(func.coalesce(func.sum(AgentRun.total_tokens), 0)).where(
                AgentRun.started_at >= since_24h
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
        "user_status_distribution": user_status_distribution,
        "user_role_distribution": user_role_distribution,
        "content_trend": content_trend,
        "music_style_distribution": music_style_distribution,
        "moderation_queue": {
            "pending_comments": int(pending_comments),
            "pending_space_posts": int(pending_space_posts),
            "pending_moderation_tasks": int(pending_moderation_tasks),
        },
        "engagement_totals": {
            "total_plays": int(total_plays),
            "total_collections": int(total_collections),
            "total_forwards": int(total_forwards),
        },
        "top_hot_music": top_hot_music,
        "agent_run_summary": {
            "total_24h": int(agent_total),
            "succeeded_24h": int(agent_succeeded),
            "failed_24h": int(agent_failed),
            "total_tokens_24h": int(total_tokens_24h),
        },
    }
