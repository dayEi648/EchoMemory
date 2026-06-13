"""AI 对话 Redis 缓存模块。

缓存用户会话列表与单会话消息列表，减少 PostgreSQL / LangGraph 读取压力。
"""

import json
import logging
from typing import Any

from echomemory_backend.core.config import settings
from echomemory_backend.core.clients.redis_client import redis_client, with_redis_retry

logger = logging.getLogger(__name__)

AI_CONVERSATION_LIST_PREFIX = "ai:conv:list"
AI_CONVERSATION_MESSAGES_PREFIX = "ai:conv:msgs"


def _build_conversation_list_key(user_id: int) -> str:
    """构造用户会话列表缓存键。"""
    return f"{AI_CONVERSATION_LIST_PREFIX}:{user_id}"


def _build_messages_key(conversation_id: int) -> str:
    """构造单会话消息列表缓存键。"""
    return f"{AI_CONVERSATION_MESSAGES_PREFIX}:{conversation_id}"


@with_redis_retry
async def get_conversation_list(user_id: int) -> list[dict[str, Any]] | None:
    """读取用户 AI 会话列表缓存。

    参数:
        user_id: 用户主键。

    返回:
        缓存命中时返回会话列表字典列表；未命中返回 None。
    """
    raw = await redis_client.get(_build_conversation_list_key(user_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("AI conversation list cache corrupted for user %s", user_id)
        return None


@with_redis_retry
async def set_conversation_list(
    user_id: int, items: list[dict[str, Any]]
) -> None:
    """写入用户 AI 会话列表缓存。

    参数:
        user_id: 用户主键。
        items: 会话列表字典列表。
    """
    await redis_client.set(
        _build_conversation_list_key(user_id),
        json.dumps(items, default=str),
        ex=settings.ai_conversation_list_cache_ttl_seconds,
    )


@with_redis_retry
async def invalidate_conversation_list(user_id: int) -> None:
    """删除用户 AI 会话列表缓存。

    参数:
        user_id: 用户主键。
    """
    await redis_client.delete(_build_conversation_list_key(user_id))


@with_redis_retry
async def get_messages(conversation_id: int) -> list[dict[str, Any]] | None:
    """读取单会话消息列表缓存。

    参数:
        conversation_id: 会话主键。

    返回:
        缓存命中时返回消息字典列表；未命中返回 None。
    """
    raw = await redis_client.get(_build_messages_key(conversation_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("AI messages cache corrupted for conversation %s", conversation_id)
        return None


@with_redis_retry
async def set_messages(
    conversation_id: int, messages: list[dict[str, Any]]
) -> None:
    """写入单会话消息列表缓存。

    参数:
        conversation_id: 会话主键。
        messages: 消息字典列表。
    """
    await redis_client.set(
        _build_messages_key(conversation_id),
        json.dumps(messages, default=str),
        ex=settings.ai_conversation_messages_cache_ttl_seconds,
    )


@with_redis_retry
async def invalidate_messages(conversation_id: int) -> None:
    """删除单会话消息列表缓存。

    参数:
        conversation_id: 会话主键。
    """
    await redis_client.delete(_build_messages_key(conversation_id))
