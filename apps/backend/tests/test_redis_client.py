import pytest
from fakeredis import FakeRedis

# We will patch the global redis_client in conftest or fixture
from echomemory_backend.core import redis_client as rc


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = FakeRedis(decode_responses=True)
    monkeypatch.setattr(rc, "redis_client", fake)
    yield fake
    fake.flushall()


class TestRefreshToken:
    def test_store_and_get(self):
        rc.store_refresh_token("rt_abc", 42)
        assert rc.get_refresh_token_user_id("rt_abc") == "42"

    def test_get_nonexistent_returns_none(self):
        assert rc.get_refresh_token_user_id("not_exists") is None

    def test_delete_removes_token(self):
        rc.store_refresh_token("rt_del", 1)
        rc.delete_refresh_token("rt_del")
        assert rc.get_refresh_token_user_id("rt_del") is None

    def test_ttl_expires(self, fake_redis):
        rc.store_refresh_token("rt_ttl", 99, ttl_seconds=1)
        assert rc.get_refresh_token_user_id("rt_ttl") == "99"
        import time

        time.sleep(1.1)
        assert rc.get_refresh_token_user_id("rt_ttl") is None


class TestBlacklist:
    def test_blacklist_and_check(self):
        rc.blacklist_access_token("at_abc")
        assert rc.is_access_token_blacklisted("at_abc") is True

    def test_non_blacklisted_returns_false(self):
        assert rc.is_access_token_blacklisted("at_clean") is False

    def test_blacklist_ttl_expires(self, fake_redis):
        rc.blacklist_access_token("at_ttl", ttl_seconds=1)
        assert rc.is_access_token_blacklisted("at_ttl") is True
        import time

        time.sleep(1.1)
        assert rc.is_access_token_blacklisted("at_ttl") is False


class TestGenerateRefreshToken:
    def test_generates_non_empty_string(self):
        token = rc.generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 20

    def test_generates_unique_tokens(self):
        t1 = rc.generate_refresh_token()
        t2 = rc.generate_refresh_token()
        assert t1 != t2
