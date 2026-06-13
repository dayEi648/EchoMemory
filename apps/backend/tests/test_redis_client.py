import asyncio

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from echomemory_backend.core.clients import redis_client as rc


@pytest.fixture(autouse=True)
def _patch_redis(fake_redis):
    """Ensure conftest.py fake_redis is active for all tests in this module."""
    pass


class TestRefreshToken:
    async def test_store_and_get(self):
        await rc.store_refresh_token("rt_abc", 42, version=3)
        assert await rc.get_refresh_token_user_id("rt_abc") == "42"
        uid, ver = await rc.get_refresh_token_data("rt_abc")
        assert uid == 42
        assert ver == 3

    async def test_get_nonexistent_returns_none(self):
        assert await rc.get_refresh_token_user_id("not_exists") is None
        assert await rc.get_refresh_token_data("not_exists") == (None, None)

    async def test_delete_removes_token(self):
        await rc.store_refresh_token("rt_del", 1, version=0)
        await rc.delete_refresh_token("rt_del")
        assert await rc.get_refresh_token_user_id("rt_del") is None

    async def test_ttl_expires(self, fake_redis):
        await rc.store_refresh_token("rt_ttl", 99, version=0, ttl_seconds=1)
        assert await rc.get_refresh_token_user_id("rt_ttl") == "99"
        await asyncio.sleep(1.1)
        assert await rc.get_refresh_token_user_id("rt_ttl") is None

    async def test_legacy_format_compat(self):
        """旧格式纯 user_id 字符串应兼容解析。"""
        await rc.redis_client.set(f"{rc.REFRESH_PREFIX}:rt_legacy", "123")
        assert await rc.get_refresh_token_user_id("rt_legacy") == "123"
        uid, ver = await rc.get_refresh_token_data("rt_legacy")
        assert uid == 123
        assert ver is None


class TestBlacklist:
    async def test_blacklist_and_check(self):
        await rc.blacklist_access_token("at_abc")
        assert await rc.is_access_token_blacklisted("at_abc") is True

    async def test_non_blacklisted_returns_false(self):
        assert await rc.is_access_token_blacklisted("at_clean") is False

    async def test_blacklist_ttl_expires(self, fake_redis):
        await rc.blacklist_access_token("at_ttl", ttl_seconds=1)
        assert await rc.is_access_token_blacklisted("at_ttl") is True
        await asyncio.sleep(1.1)
        assert await rc.is_access_token_blacklisted("at_ttl") is False

    async def test_refresh_blacklist(self):
        await rc.blacklist_refresh_token("rt_banned")
        assert await rc.is_refresh_token_blacklisted("rt_banned") is True
        assert await rc.is_refresh_token_blacklisted("rt_clean") is False


class TestUserTokenVersion:
    async def test_get_default_version(self):
        assert await rc.get_user_token_version(999) == 0

    async def test_increment_and_get(self):
        v1 = await rc.increment_user_token_version(1)
        assert v1 == 1
        assert await rc.get_user_token_version(1) == 1

        v2 = await rc.increment_user_token_version(1)
        assert v2 == 2
        assert await rc.get_user_token_version(1) == 2

    async def test_isolated_per_user(self):
        await rc.increment_user_token_version(10)
        await rc.increment_user_token_version(10)
        await rc.increment_user_token_version(20)
        assert await rc.get_user_token_version(10) == 2
        assert await rc.get_user_token_version(20) == 1


class TestGenerateRefreshToken:
    async def test_generates_non_empty_string(self):
        token = rc.generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 20

    async def test_generates_unique_tokens(self):
        t1 = rc.generate_refresh_token()
        t2 = rc.generate_refresh_token()
        assert t1 != t2


class TestRateLimit:
    async def test_allows_requests_within_limit(self):
        key = "test_allow"
        for _ in range(3):
            assert await rc.check_rate_limit(key, max_requests=3, window_seconds=60) is True

    async def test_blocks_requests_over_limit(self):
        key = "test_block"
        assert await rc.check_rate_limit(key, max_requests=2, window_seconds=60) is True
        assert await rc.check_rate_limit(key, max_requests=2, window_seconds=60) is True
        assert await rc.check_rate_limit(key, max_requests=2, window_seconds=60) is False

    async def test_sliding_window_expires_old_entries(self, fake_redis):
        key = "test_window"
        redis_key = f"rate_limit:{key}"
        await fake_redis.zadd(redis_key, {"stale": 1})
        assert await rc.check_rate_limit(key, max_requests=1, window_seconds=60) is True
        assert await rc.check_rate_limit(key, max_requests=1, window_seconds=60) is False


class TestRedisRetry:
    async def test_retries_transient_failure(self, monkeypatch):
        calls = {"count": 0}

        async def flaky_get(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RedisConnectionError("boom")
            return None

        monkeypatch.setattr(rc.redis_client, "get", flaky_get)
        assert await rc.get_refresh_token_user_id("retry_token") is None
        assert calls["count"] == 3
