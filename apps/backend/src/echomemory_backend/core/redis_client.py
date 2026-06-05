import secrets

import redis

from echomemory_backend.core.config import settings

# Redis key prefixes
REFRESH_PREFIX = "refresh"
BLACKLIST_PREFIX = "blacklist"

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def store_refresh_token(
    token: str, user_id: int | str, ttl_seconds: int = 30 * 24 * 3600
) -> None:
    """Store refresh token in Redis with TTL (default 30 days)."""
    redis_client.set(f"{REFRESH_PREFIX}:{token}", str(user_id), ex=ttl_seconds)


def get_refresh_token_user_id(token: str) -> str | None:
    """Get user_id associated with refresh token. Returns None if expired or invalid."""
    return redis_client.get(f"{REFRESH_PREFIX}:{token}")


def delete_refresh_token(token: str) -> None:
    """Delete refresh token from Redis (used on logout or token rotation)."""
    redis_client.delete(f"{REFRESH_PREFIX}:{token}")


def blacklist_access_token(token: str, ttl_seconds: int = 24 * 3600) -> None:
    """Blacklist an access token with TTL matching its remaining lifetime (default 1 day)."""
    redis_client.set(f"{BLACKLIST_PREFIX}:{token}", "1", ex=ttl_seconds)


def is_access_token_blacklisted(token: str) -> bool:
    """Check if an access token has been blacklisted (e.g. after logout)."""
    return redis_client.exists(f"{BLACKLIST_PREFIX}:{token}") == 1


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random refresh token string."""
    return secrets.token_urlsafe(32)
