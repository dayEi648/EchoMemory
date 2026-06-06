import secrets

import redis

from echomemory_backend.core.config import settings

# Redis 键前缀
REFRESH_PREFIX = "refresh"
BLACKLIST_PREFIX = "blacklist"

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def store_refresh_token(
    token: str, user_id: int | str, ttl_seconds: int = 30 * 24 * 3600
) -> None:
    """将 refresh token 存入 Redis 并设置 TTL（默认 30 天）。"""
    redis_client.set(f"{REFRESH_PREFIX}:{token}", str(user_id), ex=ttl_seconds)


def get_refresh_token_user_id(token: str) -> str | None:
    """获取与 refresh token 关联的用户 ID。若已过期或无效则返回 None。"""
    return redis_client.get(f"{REFRESH_PREFIX}:{token}")


def delete_refresh_token(token: str) -> None:
    """从 Redis 中删除 refresh token（在登出或 token 轮换时使用）。"""
    redis_client.delete(f"{REFRESH_PREFIX}:{token}")


def blacklist_access_token(token: str, ttl_seconds: int = 24 * 3600) -> None:
    """将 access token 加入黑名单，TTL 默认 1 天。"""
    redis_client.set(f"{BLACKLIST_PREFIX}:{token}", "1", ex=ttl_seconds)


def is_access_token_blacklisted(token: str) -> bool:
    """检查 access token 是否已被加入黑名单（如登出后）。"""
    return redis_client.exists(f"{BLACKLIST_PREFIX}:{token}") == 1


def generate_refresh_token() -> str:
    """生成加密安全的随机 refresh token 字符串。"""
    return secrets.token_urlsafe(32)
