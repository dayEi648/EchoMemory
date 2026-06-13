"""业务缓存工具模块。

提供统一的 Redis 缓存读写、键名规范、JSON 序列化、空值缓存与模式删除能力。
所有业务缓存应通过本模块操作，避免直接调用 Redis 客户端。
"""

import json
import logging
from datetime import date, datetime
from typing import Any

from echomemory_backend.core import redis_client as redis_client_module
from echomemory_backend.core.redis_client import with_redis_retry

logger = logging.getLogger(__name__)


def _redis_client():
    """获取当前 Redis 客户端实例。

    通过模块属性访问，便于测试时通过 monkeypatch 替换为 FakeRedis。
    """
    return redis_client_module.redis_client

# 空值缓存标记：用于缓存“查询结果不存在”的状态，防止缓存穿透。
# 使用带项目前缀的随机值，避免与用户真实数据冲突。
CACHE_NONE_MARKER = "__ECHOMEMORY_CACHE_NONE_v1__"

# ---------------------------------------------------------------------------
# 业务缓存键前缀
# ---------------------------------------------------------------------------
MUSIC_DETAIL_PREFIX = "music:detail"
ALBUM_DETAIL_PREFIX = "album:detail"
PLAYLIST_DETAIL_PREFIX = "playlist:detail"
USER_PUBLIC_PREFIX = "user:public"
CHART_HOT_SONGS_PREFIX = "chart:hot_songs"
CHART_NEW_SONGS_PREFIX = "chart:new_songs"
HOME_RECOMMENDED_ALBUMS_PREFIX = "home:recommended_albums"
MUSIC_LYRICS_PREFIX = "music:lyrics"
ADMIN_DASHBOARD_STATS_PREFIX = "admin:dashboard:stats"
DAILY_RECOMMENDATION_PREFIX = "recommend:daily"
RADAR_RECOMMENDATION_PREFIX = "recommend:radar"
RECOMMEND_CHART_PREFIX = "recommend:chart"


class _CacheMiss:
    """缓存未命中的哨兵对象，用于区分"key 不存在"与"缓存值为 None"。"""

    pass


CACHE_MISS = _CacheMiss()


class _CacheJSONEncoder(json.JSONEncoder):
    """扩展 JSON 编码器，支持 datetime/date 对象序列化为 ISO 8601 字符串。"""

    def default(self, obj: Any) -> Any:
        """将 datetime/date 转为 ISO 格式；其余对象走默认序列化。"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def build_cache_key(*parts: Any) -> str:
    """使用冒号拼接缓存键。

    Args:
        *parts: 键的各层级，如 ("music:detail", 123)。

    Returns:
        拼接后的缓存键字符串。
    """
    return ":".join(str(part) for part in parts)


@with_redis_retry
async def cache_get(key: str) -> Any | _CacheMiss:
    """从 Redis 读取缓存值并反序列化。

    Args:
        key: 缓存键。

    Returns:
        缓存值；若缓存的是空值标记则返回 None；若 key 不存在则返回 CACHE_MISS。
    """
    client = _redis_client()
    raw = await client.get(key)
    if raw is None:
        return CACHE_MISS
    if raw == CACHE_NONE_MARKER:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("缓存值 JSON 解析失败，删除脏数据: %s", key)
        await client.delete(key)
        return CACHE_MISS


@with_redis_retry
async def cache_set(
    key: str,
    value: Any,
    ttl_seconds: int,
    *,
    none_ttl_seconds: int = 60,
) -> None:
    """将值序列化后写入 Redis，并设置过期时间。

    当 value 为 None 时，写入空值标记（CACHE_NONE_MARKER）并使用较短的 TTL，
    用于防止缓存穿透。

    Args:
        key: 缓存键。
        value: 要缓存的值；为 None 时缓存空值标记。
        ttl_seconds: 正常值的过期时间（秒）。
        none_ttl_seconds: 空值标记的过期时间（秒），默认 60 秒。
    """
    client = _redis_client()
    if value is None:
        await client.set(key, CACHE_NONE_MARKER, ex=none_ttl_seconds)
        return
    payload = json.dumps(value, ensure_ascii=False, cls=_CacheJSONEncoder)
    await client.set(key, payload, ex=ttl_seconds)


@with_redis_retry
async def cache_delete(key: str) -> None:
    """删除指定缓存键。

    Args:
        key: 要删除的缓存键。
    """
    await _redis_client().delete(key)


@with_redis_retry
async def cache_delete_pattern(pattern: str) -> None:
    """按模式批量删除缓存键。

    使用 SCAN 迭代匹配 key，再逐个删除，避免在生产环境使用 KEYS 造成阻塞。

    Args:
        pattern: Redis key 匹配模式，如 "chart:*"。
    """
    client = _redis_client()
    async for key in client.scan_iter(match=pattern):
        await client.delete(key)
