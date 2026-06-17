"""业务缓存服务模块。

提供音乐、专辑、歌单、用户公开资料等高频详情对象的缓存读写与失效辅助函数。
所有函数只操作公共字段，不包含当前用户状态（如 is_collected_by_me）。
"""

from datetime import datetime, timedelta, timezone

from echomemory_backend.core.cache.general import (
    ADMIN_DASHBOARD_STATS_PREFIX,
    ALBUM_DETAIL_PREFIX,
    CACHE_MISS,
    DAILY_RECOMMENDATION_PREFIX,
    MUSIC_DETAIL_PREFIX,
    PLAYLIST_DETAIL_PREFIX,
    RADAR_RECOMMENDATION_PREFIX,
    RECOMMEND_CHART_PREFIX,
    USER_PUBLIC_PREFIX,
    build_cache_key,
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
)
from echomemory_backend.schemas.album import AlbumOut
from echomemory_backend.schemas.music import MusicOut, RecommendChartListOut
from echomemory_backend.schemas.playlist import PlaylistOut
from echomemory_backend.schemas.user import UserPublicOut

# 详情对象缓存 TTL（秒）
_MUSIC_DETAIL_TTL = 30 * 60       # 30 分钟
_ALBUM_DETAIL_TTL = 30 * 60       # 30 分钟
_PLAYLIST_DETAIL_TTL = 5 * 60     # 5 分钟
_USER_PUBLIC_TTL = 30 * 60        # 30 分钟


# ---------------------------------------------------------------------------
# 音乐详情缓存
# ---------------------------------------------------------------------------

async def get_cached_music_detail(music_id: int) -> MusicOut | None:
    """从缓存读取音乐详情。

    Args:
        music_id: 音乐主键 ID。

    Returns:
        缓存中的 MusicOut 实例；未命中时返回 None。
    """
    cached = await cache_get(build_cache_key(MUSIC_DETAIL_PREFIX, music_id))
    if cached is CACHE_MISS:
        return None
    return MusicOut.model_validate(cached)


async def set_cached_music_detail(music_out: MusicOut) -> None:
    """将音乐详情写入缓存。

    Args:
        music_out: 要缓存的音乐详情 Schema 实例。
    """
    await cache_set(
        build_cache_key(MUSIC_DETAIL_PREFIX, music_out.id),
        music_out.model_dump(),
        _MUSIC_DETAIL_TTL,
    )


async def invalidate_music_detail(music_id: int) -> None:
    """失效指定音乐详情缓存。

    Args:
        music_id: 音乐主键 ID。
    """
    await cache_delete(build_cache_key(MUSIC_DETAIL_PREFIX, music_id))


# ---------------------------------------------------------------------------
# 专辑详情缓存
# ---------------------------------------------------------------------------

async def get_cached_album_detail(album_id: int) -> AlbumOut | None:
    """从缓存读取专辑详情。

    Args:
        album_id: 专辑主键 ID。

    Returns:
        缓存中的 AlbumOut 实例；未命中时返回 None。
    """
    cached = await cache_get(build_cache_key(ALBUM_DETAIL_PREFIX, album_id))
    if cached is CACHE_MISS:
        return None
    return AlbumOut.model_validate(cached)


async def set_cached_album_detail(album_out: AlbumOut) -> None:
    """将专辑详情写入缓存。

    Args:
        album_out: 要缓存的专辑详情 Schema 实例。
    """
    await cache_set(
        build_cache_key(ALBUM_DETAIL_PREFIX, album_out.id),
        album_out.model_dump(),
        _ALBUM_DETAIL_TTL,
    )


async def invalidate_album_detail(album_id: int) -> None:
    """失效指定专辑详情缓存。

    Args:
        album_id: 专辑主键 ID。
    """
    await cache_delete(build_cache_key(ALBUM_DETAIL_PREFIX, album_id))


# ---------------------------------------------------------------------------
# 歌单详情缓存
# ---------------------------------------------------------------------------

async def get_cached_playlist_detail(playlist_id: int) -> PlaylistOut | None:
    """从缓存读取歌单详情。

    Args:
        playlist_id: 歌单主键 ID。

    Returns:
        缓存中的 PlaylistOut 实例；未命中时返回 None。
    """
    cached = await cache_get(build_cache_key(PLAYLIST_DETAIL_PREFIX, playlist_id))
    if cached is CACHE_MISS:
        return None
    return PlaylistOut.model_validate(cached)


async def set_cached_playlist_detail(playlist_out: PlaylistOut) -> None:
    """将歌单详情写入缓存。

    Args:
        playlist_out: 要缓存的歌单详情 Schema 实例。
    """
    await cache_set(
        build_cache_key(PLAYLIST_DETAIL_PREFIX, playlist_out.id),
        playlist_out.model_dump(),
        _PLAYLIST_DETAIL_TTL,
    )


async def invalidate_playlist_detail(playlist_id: int) -> None:
    """失效指定歌单详情缓存。

    Args:
        playlist_id: 歌单主键 ID。
    """
    await cache_delete(build_cache_key(PLAYLIST_DETAIL_PREFIX, playlist_id))


# ---------------------------------------------------------------------------
# 用户公开资料缓存
# ---------------------------------------------------------------------------

async def get_cached_user_public(user_id: int) -> UserPublicOut | None:
    """从缓存读取用户公开资料。

    Args:
        user_id: 用户主键 ID。

    Returns:
        缓存中的 UserPublicOut 实例；未命中时返回 None。
    """
    cached = await cache_get(build_cache_key(USER_PUBLIC_PREFIX, user_id))
    if cached is CACHE_MISS:
        return None
    return UserPublicOut.model_validate(cached)


async def set_cached_user_public(user_out: UserPublicOut) -> None:
    """将用户公开资料写入缓存。

    Args:
        user_out: 要缓存的用户公开资料 Schema 实例。
    """
    await cache_set(
        build_cache_key(USER_PUBLIC_PREFIX, user_out.id),
        user_out.model_dump(),
        _USER_PUBLIC_TTL,
    )


async def invalidate_user_public(user_id: int) -> None:
    """失效指定用户公开资料缓存。

    Args:
        user_id: 用户主键 ID。
    """
    await cache_delete(build_cache_key(USER_PUBLIC_PREFIX, user_id))


# ---------------------------------------------------------------------------
# 管理仪表盘统计缓存
# ---------------------------------------------------------------------------

_ADMIN_DASHBOARD_STATS_TTL = 5 * 60  # 5 分钟


async def get_cached_dashboard_stats() -> dict[str, int] | None:
    """从缓存读取管理仪表盘统计数据。

    Returns:
        缓存中的统计字典；未命中时返回 None。
    """
    cached = await cache_get(build_cache_key(ADMIN_DASHBOARD_STATS_PREFIX))
    if cached is CACHE_MISS:
        return None
    return cached


async def set_cached_dashboard_stats(stats: dict[str, int]) -> None:
    """将管理仪表盘统计数据写入缓存。

    Args:
        stats: 仪表盘统计字典。
    """
    await cache_set(
        build_cache_key(ADMIN_DASHBOARD_STATS_PREFIX), stats, _ADMIN_DASHBOARD_STATS_TTL
    )


async def invalidate_dashboard_stats() -> None:
    """失效管理仪表盘统计缓存。"""
    await cache_delete(build_cache_key(ADMIN_DASHBOARD_STATS_PREFIX))


# ---------------------------------------------------------------------------
# 推荐缓存
# ---------------------------------------------------------------------------

def _recommendation_cache_ttl_seconds() -> int:
    """计算推荐缓存的剩余有效秒数。

    推荐结果在每天 6:00 UTC 刷新，因此 TTL 设为到下一个 6:00 UTC 的秒数。

    Returns:
        剩余秒数。
    """
    now = datetime.now(timezone.utc)
    next_refresh = now.replace(hour=6, minute=0, second=0, microsecond=0)
    if next_refresh <= now:
        next_refresh = next_refresh + timedelta(days=1)
    return int((next_refresh - now).total_seconds())


async def get_cached_daily_recommendation(user_id: int) -> dict | None:
    """从缓存读取用户每日推荐结果。"""
    cached = await cache_get(build_cache_key(DAILY_RECOMMENDATION_PREFIX, user_id))
    if cached is CACHE_MISS:
        return None
    return cached


async def set_cached_daily_recommendation(user_id: int, payload: dict) -> None:
    """将用户每日推荐结果写入缓存。"""
    await cache_set(
        build_cache_key(DAILY_RECOMMENDATION_PREFIX, user_id),
        payload,
        _recommendation_cache_ttl_seconds(),
    )


async def get_cached_radar_recommendation(user_id: int) -> dict | None:
    """从缓存读取用户私人雷达结果。"""
    cached = await cache_get(build_cache_key(RADAR_RECOMMENDATION_PREFIX, user_id))
    if cached is CACHE_MISS:
        return None
    return cached


async def set_cached_radar_recommendation(user_id: int, payload: dict) -> None:
    """将用户私人雷达结果写入缓存。"""
    await cache_set(
        build_cache_key(RADAR_RECOMMENDATION_PREFIX, user_id),
        payload,
        _recommendation_cache_ttl_seconds(),
    )


async def get_cached_recommendation_chart(date_str: str) -> dict | None:
    """从缓存读取指定日期的推荐榜。"""
    cached = await cache_get(build_cache_key(RECOMMEND_CHART_PREFIX, date_str))
    if cached is CACHE_MISS:
        return None
    return cached


async def set_cached_recommendation_chart(date_str: str, payload: dict) -> None:
    """将指定日期的推荐榜写入缓存。"""
    await cache_set(
        build_cache_key(RECOMMEND_CHART_PREFIX, date_str),
        payload,
        _recommendation_cache_ttl_seconds(),
    )


async def invalidate_recommendation_caches() -> None:
    """失效所有推荐相关缓存。"""
    await cache_delete_pattern(f"{DAILY_RECOMMENDATION_PREFIX}:*")
    await cache_delete_pattern(f"{RADAR_RECOMMENDATION_PREFIX}:*")
    await cache_delete_pattern(f"{RECOMMEND_CHART_PREFIX}:*")
