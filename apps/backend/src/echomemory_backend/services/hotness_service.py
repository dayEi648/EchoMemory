"""热度自动计算与维护服务模块。

对 Music、Album、Playlist 的 ``hot`` 字段进行基于近期参与度 + 时间衰减的自动计算。
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.music import Music
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.services.cache_service import (
    invalidate_album_detail,
    invalidate_music_detail,
    invalidate_playlist_detail,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 可调参数
# ---------------------------------------------------------------------------

_RECENT_WINDOW_DAYS = 7          # 近期播放窗口（天）
_W_PLAY = 10                     # 单次播放权重
_W_COLLECT = 5                   # 单次收藏权重
_W_COMMENT = 3                   # 单条评论权重
_TIME_DECAY_EXPONENT = 0.6       # 时间衰减指数（<1 平缓，>1 陡峭）
_MAX_HOT = 1000                  # 热度上限

_BATCH_SIZE = 200                # 全量重算时每批处理数
_BATCH_INTERVAL_SECONDS = 0.5    # 批次间隔


# ---------------------------------------------------------------------------
# 单实体计算
# ---------------------------------------------------------------------------


async def recalculate_music_hot(db: AsyncSession, music_id: int) -> None:
    """重新计算单首音乐的 hot 值。

    热度公式：
        recent = COUNT(play_history WHERE music_id=X AND played_at > NOW - 7天)
        engagement = ln(recent * W_PLAY + collect_count * W_COLLECT
                        + comment_count * W_COMMENT + 1)
        age_days = max(1, (NOW - release_date或created_at).days)
        hot = min(MAX, int(engagement * 100 / age_days^DECAY))

    Args:
        db: SQLAlchemy 异步 Session。
        music_id: 目标音乐主键。
    """
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=_RECENT_WINDOW_DAYS)

    # 近 7 天播放次数
    recent_plays = (
        await db.execute(
            select(func.count()).where(
                PlayHistory.music_id == music_id,
                PlayHistory.played_at >= recent_cutoff,
            )
        )
    ).scalar_one()

    music = await db.get(Music, music_id)
    if music is None:
        return

    engagement = math.log(
        recent_plays * _W_PLAY
        + music.collect_count * _W_COLLECT
        + music.comment_count * _W_COMMENT
        + 1
    )

    ref_date = music.release_date or music.created_at.date() if music.created_at else now.date()
    age_days = max(1, (now.date() - ref_date).days)

    hot = min(_MAX_HOT, int(engagement * 100 / (age_days ** _TIME_DECAY_EXPONENT)))

    await db.execute(update(Music).where(Music.id == music_id).values(hot=hot))
    await invalidate_music_detail(music_id)


async def recalculate_album_hot(db: AsyncSession, album_id: int) -> None:
    """重新计算专辑的 hot 值（取所包含音乐 hot 的平均值）。

    Args:
        db: SQLAlchemy 异步 Session。
        album_id: 目标专辑主键。
    """
    avg = (
        await db.execute(
            select(func.coalesce(func.avg(Music.hot), 0))
            .select_from(AlbumMusic)
            .join(Music, Music.id == AlbumMusic.music_id)
            .where(AlbumMusic.album_id == album_id)
        )
    ).scalar_one()
    await db.execute(
        update(Album).where(Album.id == album_id).values(hot=int(avg))
    )
    await invalidate_album_detail(album_id)


async def recalculate_playlist_hot(db: AsyncSession, playlist_id: int) -> None:
    """重新计算歌单的 hot 值（取所包含音乐 hot 的平均值）。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 目标歌单主键。
    """
    avg = (
        await db.execute(
            select(func.coalesce(func.avg(Music.hot), 0))
            .select_from(PlaylistMusic)
            .join(Music, Music.id == PlaylistMusic.music_id)
            .where(PlaylistMusic.playlist_id == playlist_id)
        )
    ).scalar_one()
    await db.execute(
        update(Playlist).where(Playlist.id == playlist_id).values(hot=int(avg))
    )
    await invalidate_playlist_detail(playlist_id)


# ---------------------------------------------------------------------------
# 全量维护
# ---------------------------------------------------------------------------


async def recalculate_all_hot(db: AsyncSession) -> dict[str, int]:
    """全量重算热度（仅已发布音乐及其所属专辑/歌单），分批执行降低锁竞争。

    返回 ``{"music": N, "album": M, "playlist": P}`` 统计。
    """
    # ---- 音乐 ----
    music_ids = (
        await db.execute(
            select(Music.id).where(Music.is_published == True).order_by(Music.id)
        )
    ).scalars().all()

    music_count = 0
    for i in range(0, len(music_ids), _BATCH_SIZE):
        batch = music_ids[i : i + _BATCH_SIZE]
        for mid in batch:
            await recalculate_music_hot(db, mid)
            music_count += 1
        await db.commit()
        if i + _BATCH_SIZE < len(music_ids):
            import asyncio
            await asyncio.sleep(_BATCH_INTERVAL_SECONDS)

    # ---- 专辑（仅未删除）----
    album_ids = (
        await db.execute(
            select(Album.id).where(Album.is_deleted == False).order_by(Album.id)
        )
    ).scalars().all()

    album_count = 0
    for aid in album_ids:
        await recalculate_album_hot(db, aid)
        album_count += 1
    await db.commit()

    # ---- 歌单 ----
    playlist_ids = (
        await db.execute(select(Playlist.id).order_by(Playlist.id))
    ).scalars().all()

    playlist_count = 0
    for pid in playlist_ids:
        await recalculate_playlist_hot(db, pid)
        playlist_count += 1
    await db.commit()

    # 热度重算完成后刷新榜单缓存，使首页榜单反映最新热度
    from echomemory_backend.services.music_service import invalidate_chart_caches

    await invalidate_chart_caches()

    logger.info(
        "Hot recalc complete: music=%d, albums=%d, playlists=%d",
        music_count, album_count, playlist_count,
    )
    return {"music": music_count, "album": album_count, "playlist": playlist_count}
