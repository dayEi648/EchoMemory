"""Inbox 实时事件 Pub/Sub 工具模块。

负责将"新通知 / 新私信 / 未读数变化"等事件以 JSON 形式发布到 Redis，
WebSocket 监听端通过订阅 ``inbox:user:{id}`` 频道实时收到推送。
"""

import json
from typing import Any

from echomemory_backend.core.redis_client import redis_client, with_redis_retry

INBOX_CHANNEL_PREFIX = "inbox:user"


def inbox_channel(user_id: int) -> str:
    """生成 Inbox 频道名。

    Args:
        user_id: 接收事件的用户主键。

    Returns:
        Redis Pub/Sub 频道名字符串。
    """
    return f"{INBOX_CHANNEL_PREFIX}:{user_id}"


async def publish_inbox_event(user_id: int, event: dict[str, Any]) -> None:
    """向指定用户的 Inbox 频道发布事件。

    Args:
        user_id: 事件接收者主键。
        event: 事件字典，必须包含 ``type`` 字段（如 ``notification`` / ``message``）。

    Returns:
        None。Redis 发布失败会抛出异常，由调用方决定是否吞掉以避免影响主业务。
    """
    payload = json.dumps(event, ensure_ascii=False, default=str)
    await _publish(inbox_channel(user_id), payload)


@with_redis_retry
async def _publish(channel: str, payload: str) -> None:
    """向 Redis Pub/Sub 频道发布消息（含重试）。"""
    await redis_client.publish(channel, payload)
