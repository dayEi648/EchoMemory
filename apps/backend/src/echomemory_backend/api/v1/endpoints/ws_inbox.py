"""Inbox WebSocket 端点，用于向当前登录用户实时推送通知与私信事件。

连接路径：``/api/v1/ws/inbox?token=<access_token>``。
鉴权流程复用 REST 接口的 JWT + Redis 黑名单 + token version 三重校验，
通过 ``inbox:user:{id}`` Redis Pub/Sub 频道接收来自业务侧的事件并转发给客户端。
"""

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.inbox.pubsub import inbox_channel
from echomemory_backend.core.clients.redis_client import (
    get_user_token_version,
    is_access_token_blacklisted,
    redis_client,
)
from echomemory_backend.core.security.security import decode_access_token
from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.enums import UserStatus
from echomemory_backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])

WS_CLOSE_AUTH_FAILED = status.WS_1008_POLICY_VIOLATION
WS_HEARTBEAT_INTERVAL_SECONDS = 30
WS_HEARTBEAT_TIMEOUT_SECONDS = 10


async def _resolve_user_from_token(token: str | None) -> User | None:
    """根据 access token 解析当前用户。鉴权失败时返回 None。

    Args:
        token: 从 query 或 subprotocol 提取的 JWT access token。

    Returns:
        校验通过的 User 实例，否则 None。
    """
    if not token:
        return None
    if await is_access_token_blacklisted(token):
        return None
    payload = decode_access_token(token)
    if payload is None:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None

    token_version = payload.get("ver")
    current_version = await get_user_token_version(user_id)
    if token_version != current_version:
        return None

    db: AsyncSession = AsyncSessionLocal()
    try:
        user = await db.get(User, user_id)
    finally:
        await db.close()
    if user is None or user.is_deleted:
        return None
    if user.status == UserStatus.BANNED:
        return None
    return user


async def _await_task_safely(task: asyncio.Task) -> None:
    """等待任务结束并吞掉已取消或已失败任务的异常。"""
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Inbox websocket task %s failed", task.get_name())


@router.websocket("/ws/inbox")
async def inbox_websocket(
    websocket: WebSocket,
    token: str = Query(...),
):
    """订阅当前用户的 Inbox 频道并实时推送事件。

    Args:
        websocket: Starlette WebSocket 实例。
        token: access token，由前端通过 query 参数提供。

    Returns:
        None。鉴权失败立即关闭连接；订阅期间客户端断线即退出。
    """
    user = await _resolve_user_from_token(token)
    if user is None:
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    await websocket.accept()
    pubsub = redis_client.pubsub()
    channel = inbox_channel(user.id)
    try:
        await pubsub.subscribe(channel)
    except Exception:
        logger.exception("Failed to subscribe inbox channel for user %s", user.id)
        await websocket.close(code=WS_CLOSE_AUTH_FAILED)
        return

    async def _forward() -> None:
        """从 Redis Pub/Sub 读取消息并转发到 WebSocket。"""
        try:
            async for raw in pubsub.listen():
                if raw is None:
                    continue
                if raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if data is None:
                    continue
                try:
                    await websocket.send_text(data)
                except Exception:
                    logger.exception("Failed to forward inbox event to WebSocket")
                    return
        except Exception:
            logger.exception("Redis pubsub listen failed for user %s", user.id)

    forward_task = asyncio.create_task(_forward(), name="inbox-forward")

    async def _client_loop() -> None:
        """检测客户端断线；定期发送心跳并在超时无响应时关闭连接。"""
        while True:
            try:
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_HEARTBEAT_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    return
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=WS_HEARTBEAT_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    return
            except WebSocketDisconnect:
                return
            except Exception:
                logger.exception("Unexpected error in inbox websocket receive loop")
                return

    client_task = asyncio.create_task(_client_loop(), name="inbox-client")
    tasks = {forward_task, client_task}
    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done | pending:
            await _await_task_safely(task)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        for task in tasks:
            await _await_task_safely(task)
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            logger.exception("Failed to unsubscribe inbox channel for user %s", user.id)
        try:
            await pubsub.aclose()
        except Exception:
            logger.exception("Failed to close pubsub for user %s", user.id)
