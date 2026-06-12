"""Redis 客户端模块，提供 refresh token 存取、黑名单管理及用户 token version 操作。"""

import asyncio
import functools
import json
import logging
import secrets
import time

from redis.asyncio import from_url
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

from echomemory_backend.core.config import settings

logger = logging.getLogger(__name__)

# Redis 键前缀
REFRESH_PREFIX = "refresh"
BLACKLIST_PREFIX = "blacklist"
USER_VERSION_PREFIX = "user_version"

REDIS_RETRY_MAX_ATTEMPTS = 3
REDIS_RETRY_BASE_DELAY_SECONDS = 0.05
_REDIS_RETRYABLE_EXCEPTIONS = (RedisConnectionError, RedisTimeoutError, RedisError)

redis_client = from_url(settings.redis_url, decode_responses=True, protocol=2)


def with_redis_retry(func):
    """为 Redis 异步操作提供指数退避重试，缓解网络抖动导致的瞬时失败。

    Args:
        func: 待包装的 async 函数。

    Returns:
        包装后的 async 函数；超出重试次数后抛出最后一次异常。
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        last_exc: Exception | None = None
        for attempt in range(REDIS_RETRY_MAX_ATTEMPTS):
            try:
                return await func(*args, **kwargs)
            except _REDIS_RETRYABLE_EXCEPTIONS as exc:
                last_exc = exc
                if attempt + 1 >= REDIS_RETRY_MAX_ATTEMPTS:
                    break
                delay = REDIS_RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning(
                    "Redis %s failed (attempt %s/%s), retrying in %.2fs: %s",
                    func.__name__,
                    attempt + 1,
                    REDIS_RETRY_MAX_ATTEMPTS,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
        assert last_exc is not None
        raise last_exc

    return wrapper


@with_redis_retry
async def store_refresh_token(
    token: str, user_id: int, version: int, ttl_seconds: int = 30 * 24 * 3600
) -> None:
    """将 refresh token 及关联版本号以 JSON 格式存入 Redis 并设置 TTL（默认 30 天）。"""
    payload = json.dumps({"user_id": user_id, "version": version})
    await redis_client.set(f"{REFRESH_PREFIX}:{token}", payload, ex=ttl_seconds)


@with_redis_retry
async def get_refresh_token_user_id(token: str) -> str | None:
    """获取与 refresh token 关联的用户 ID（兼容旧格式纯 user_id 字符串）。"""
    raw = await redis_client.get(f"{REFRESH_PREFIX}:{token}")
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return str(data["user_id"])
        # 兼容旧格式：json.loads 将纯数字字符串解析为 int
        return str(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        # 兼容旧格式：纯 user_id 字符串
        return raw


@with_redis_retry
async def get_refresh_token_data(token: str) -> tuple[int | None, int | None]:
    """解析 refresh token 存储的 JSON 数据，返回 (user_id, version)。

    旧格式（纯 user_id 字符串）返回 (user_id, None)。
    """
    raw = await redis_client.get(f"{REFRESH_PREFIX}:{token}")
    if raw is None:
        return None, None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return int(data["user_id"]), int(data["version"])
        # 兼容旧格式：json.loads 将纯数字字符串解析为 int
        return int(data), None
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        # 兼容旧格式
        try:
            return int(raw), None
        except ValueError:
            return None, None


@with_redis_retry
async def delete_refresh_token(token: str) -> None:
    """从 Redis 中删除 refresh token（在登出或 token 轮换时使用）。"""
    await redis_client.delete(f"{REFRESH_PREFIX}:{token}")


@with_redis_retry
async def blacklist_access_token(token: str, ttl_seconds: int | None = None) -> None:
    """将 access token 加入黑名单，TTL 默认与 JWT 过期时间一致。"""
    if ttl_seconds is None:
        ttl_seconds = settings.jwt_access_token_expire_minutes * 60
    await redis_client.set(f"{BLACKLIST_PREFIX}:{token}", "1", ex=ttl_seconds)


@with_redis_retry
async def is_access_token_blacklisted(token: str) -> bool:
    """检查 access token 是否已被加入黑名单（如登出后）。"""
    return await redis_client.exists(f"{BLACKLIST_PREFIX}:{token}") == 1


@with_redis_retry
async def blacklist_refresh_token(token: str, ttl_seconds: int | None = None) -> None:
    """将 refresh token 加入黑名单，TTL 默认与 refresh token 存活时间一致（30 天）。"""
    if ttl_seconds is None:
        ttl_seconds = 30 * 24 * 3600
    await redis_client.set(f"{BLACKLIST_PREFIX}:refresh:{token}", "1", ex=ttl_seconds)


@with_redis_retry
async def is_refresh_token_blacklisted(token: str) -> bool:
    """检查 refresh token 是否已被加入黑名单。"""
    return await redis_client.exists(f"{BLACKLIST_PREFIX}:refresh:{token}") == 1


@with_redis_retry
async def get_user_token_version(user_id: int) -> int:
    """获取用户当前的 token version，不存在则返回 0。"""
    raw = await redis_client.get(f"{USER_VERSION_PREFIX}:{user_id}")
    return int(raw) if raw is not None else 0


@with_redis_retry
async def increment_user_token_version(user_id: int) -> int:
    """原子递增用户的 token version 并返回新值。"""
    new_version = await redis_client.incr(f"{USER_VERSION_PREFIX}:{user_id}")
    return int(new_version)


@with_redis_retry
async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> bool:
    """基于 Redis Sorted Set 的滑动窗口限流。

    Args:
        key: 限流标识（如 IP、用户 ID）。
        max_requests: 窗口内最大请求次数。
        window_seconds: 窗口时长（秒）。

    Returns:
        允许请求返回 True，超过限制返回 False。
    """
    redis_key = f"rate_limit:{key}"
    now_ms = int(time.time() * 1000)
    window_start_ms = now_ms - window_seconds * 1000
    member = f"{now_ms}:{secrets.token_hex(4)}"

    await redis_client.zremrangebyscore(redis_key, 0, window_start_ms)
    count = await redis_client.zcard(redis_key)
    if count >= max_requests:
        return False
    await redis_client.zadd(redis_key, {member: now_ms})
    await redis_client.expire(redis_key, window_seconds)
    return True


def generate_refresh_token() -> str:
    """生成加密安全的随机 refresh token 字符串。"""
    return secrets.token_urlsafe(32)
