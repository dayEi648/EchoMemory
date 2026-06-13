"""业务缓存工具模块测试。"""

from datetime import date, datetime, timedelta, timezone

import pytest

from echomemory_backend.core.cache import (
    CACHE_MISS,
    CACHE_NONE_MARKER,
    build_cache_key,
    cache_delete,
    cache_delete_pattern,
    cache_get,
    cache_set,
)


@pytest.mark.anyio
async def test_cache_set_and_get(fake_redis):
    """验证正常值的缓存写入与读取。"""
    await cache_set("test:key", {"a": 1, "b": "中文字符"}, ttl_seconds=60)
    result = await cache_get("test:key")
    assert result == {"a": 1, "b": "中文字符"}


@pytest.mark.anyio
async def test_cache_get_returns_miss_when_key_missing(fake_redis):
    """未命中时应返回 CACHE_MISS 哨兵对象。"""
    result = await cache_get("test:missing")
    assert result is CACHE_MISS


@pytest.mark.anyio
async def test_cache_none_value(fake_redis):
    """缓存 None 时应写入空值标记，读取时返回 None 且不会穿透。"""
    await cache_set("test:none", None, ttl_seconds=60)

    raw = await fake_redis.get("test:none")
    assert raw == CACHE_NONE_MARKER

    result = await cache_get("test:none")
    assert result is None


@pytest.mark.anyio
async def test_cache_ttl(fake_redis):
    """验证 TTL 被正确设置，key 失效后返回 CACHE_MISS。"""
    await cache_set("test:ttl", "value", ttl_seconds=60)
    assert await cache_get("test:ttl") == "value"

    ttl = await fake_redis.ttl("test:ttl")
    assert ttl > 0

    await fake_redis.delete("test:ttl")
    assert await cache_get("test:ttl") is CACHE_MISS


@pytest.mark.anyio
async def test_cache_delete(fake_redis):
    """验证删除指定 key。"""
    await cache_set("test:delete", "value", ttl_seconds=60)
    assert await cache_get("test:delete") == "value"

    await cache_delete("test:delete")
    assert await cache_get("test:delete") is CACHE_MISS


@pytest.mark.anyio
async def test_cache_delete_pattern(fake_redis):
    """验证按模式批量删除。"""
    await cache_set("pattern:a:1", "1", ttl_seconds=60)
    await cache_set("pattern:a:2", "2", ttl_seconds=60)
    await cache_set("pattern:b:1", "3", ttl_seconds=60)
    await cache_set("other:1", "4", ttl_seconds=60)

    await cache_delete_pattern("pattern:a:*")

    assert await cache_get("pattern:a:1") is CACHE_MISS
    assert await cache_get("pattern:a:2") is CACHE_MISS
    assert await cache_get("pattern:b:1") == "3"
    assert await cache_get("other:1") == "4"


@pytest.mark.anyio
async def test_cache_datetime_serialization(fake_redis):
    """验证 datetime/date 类型可被正确序列化与反序列化为 ISO 字符串。"""
    dt = datetime(2026, 6, 13, 12, 0, 0, tzinfo=timezone.utc)
    d = date(2026, 6, 13)
    value = {"created_at": dt, "release": d}

    await cache_set("test:datetime", value, ttl_seconds=60)
    result = await cache_get("test:datetime")

    assert result["created_at"] == dt.isoformat()
    assert result["release"] == d.isoformat()


@pytest.mark.anyio
async def test_build_cache_key(fake_redis):
    """验证缓存键拼接。"""
    assert build_cache_key("music", "detail", 123) == "music:detail:123"
    assert build_cache_key("chart:hot_songs", 5) == "chart:hot_songs:5"
