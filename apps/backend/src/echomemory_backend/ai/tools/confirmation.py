"""AI 写操作二次确认凭证。"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, TypedDict

from jose import JWTError, jwt

from echomemory_backend.core.clients import redis_client as redis_module
from echomemory_backend.core.config import settings

ConfirmationResourceType = Literal["music", "playlist", "album"]
ConfirmationAction = Literal["collect", "uncollect"]

_TOKEN_TYPE = "ai_tool_confirmation"
_TOKEN_TTL_SECONDS = 5 * 60
_CONSUMED_KEY_PREFIX = "ai_tool_confirmation:consumed"


class ConfirmationPayload(TypedDict):
    """校验后的确认凭证内容。"""

    user_id: int
    resource_type: ConfirmationResourceType
    resource_id: int
    action: ConfirmationAction
    jti: str
    exp: int


def create_confirmation_token(
    *,
    user_id: int,
    resource_type: ConfirmationResourceType,
    resource_id: int,
    action: ConfirmationAction,
) -> str:
    """创建绑定用户、资源和动作的短期确认凭证。"""
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_TOKEN_TTL_SECONDS)
    payload = {
        "type": _TOKEN_TYPE,
        "sub": str(user_id),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "action": action,
        "jti": secrets.token_urlsafe(18),
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_confirmation_token(
    token: str,
    *,
    expected_user_id: int,
) -> ConfirmationPayload | None:
    """解码确认凭证并校验其所属用户与字段白名单。"""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != _TOKEN_TYPE:
            return None
        if int(payload.get("sub", 0)) != expected_user_id:
            return None
        resource_type = payload.get("resource_type")
        action = payload.get("action")
        if resource_type not in {"music", "playlist", "album"}:
            return None
        if action not in {"collect", "uncollect"}:
            return None
        resource_id = int(payload.get("resource_id", 0))
        if resource_id < 1:
            return None
        jti = payload.get("jti")
        exp = int(payload.get("exp", 0))
        if not isinstance(jti, str) or not jti or exp < 1:
            return None
        return ConfirmationPayload(
            user_id=expected_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            jti=jti,
            exp=exp,
        )
    except (JWTError, TypeError, ValueError):
        return None


async def reserve_confirmation(payload: ConfirmationPayload) -> bool:
    """原子占用确认凭证，防止重复或并发执行。"""
    now = int(datetime.now(timezone.utc).timestamp())
    ttl = max(1, payload["exp"] - now)
    key = f"{_CONSUMED_KEY_PREFIX}:{payload['jti']}"
    result = await redis_module.redis_client.set(key, "1", ex=ttl, nx=True)
    return bool(result)


async def release_confirmation(payload: ConfirmationPayload) -> None:
    """写操作失败时释放确认凭证，允许用户重试。"""
    key = f"{_CONSUMED_KEY_PREFIX}:{payload['jti']}"
    await redis_module.redis_client.delete(key)
