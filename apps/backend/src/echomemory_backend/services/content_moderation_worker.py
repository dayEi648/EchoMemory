"""内容审核后台 Worker。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from echomemory_backend.ai.graphs.content_moderation import evaluate_content
from echomemory_backend.ai.monitoring.context import AgentMonitorSession
from echomemory_backend.ai.monitoring.runtime import bind_monitor
from echomemory_backend.core.config import settings
from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.content_moderation import ContentModerationTask
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User
from echomemory_backend.services.content_moderation_service import (
    apply_moderation_decision,
    cancel_moderation_task,
    claim_pending_tasks,
    mark_moderation_attempt_failed,
)

logger = logging.getLogger(__name__)
_worker_task: asyncio.Task[None] | None = None


def _extract_moderation_text(
    content: Comment | SpacePost | Playlist | User,
    content_type: str,
) -> str:
    """从被审核内容中提取待评估文本。"""
    if content_type == "playlist":
        parts = [content.title]  # type: ignore[union-attr]
        if content.description:  # type: ignore[union-attr]
            parts.append(content.description)  # type: ignore[union-attr]
        return "\n\n".join(parts)
    if content_type == "user_profile":
        parts = [content.nickname]  # type: ignore[union-attr]
        if content.bio:  # type: ignore[union-attr]
            parts.append(content.bio)  # type: ignore[union-attr]
        return "\n\n".join(parts)
    return content.content or ""  # type: ignore[union-attr]


async def _load_subject(task: ContentModerationTask):
    """加载任务对应内容和作者快照。"""
    from echomemory_backend.models.playlist import Playlist
    from echomemory_backend.models.user import User as UserModel

    model_map = {
        "comment": Comment,
        "space_post": SpacePost,
        "playlist": Playlist,
        "user_profile": UserModel,
    }
    model = model_map.get(task.content_type)
    if model is None:
        return None

    async with AsyncSessionLocal() as db:
        content = (
            await db.execute(
                select(model)
                .where(model.id == task.content_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if content is None:
            return None

        # 读取审核版本号（处理不同列名）
        mod_version = (
            content.profile_moderation_version
            if task.content_type == "user_profile"
            else content.moderation_version
        )
        if mod_version != task.moderation_version:
            return None

        # 设置审核状态为处理中
        if task.content_type == "user_profile":
            content.profile_moderation_status = "PROCESSING"
        else:
            content.moderation_status = "PROCESSING"

        # 读取作者信息
        owner_id = content.id if task.content_type == "user_profile" else content.user_id
        username = await db.scalar(
            select(User.username).where(User.id == owner_id)
        )
        await db.commit()

        text = _extract_moderation_text(content, task.content_type)
        if not text:
            return None
        return owner_id, username, text


async def process_moderation_task(task: ContentModerationTask) -> None:
    """执行一条审核任务并完整记录监控。"""
    subject = await _load_subject(task)
    if subject is None:
        async with AsyncSessionLocal() as db:
            await cancel_moderation_task(
                db,
                task_id=task.id,
                reason="content missing or moderation version is stale",
            )
        return
    user_id, username, content = subject
    monitor = AgentMonitorSession(
        scenario="content_moderation",
        workflow_type="workflow",
        workflow_name="content_moderation",
        workflow_version="1",
        actor_user_id=user_id,
        actor_username=username,
        subject_type=task.content_type,
        subject_id=str(task.content_id),
        model=settings.content_moderation_model,
        metadata={
            "task_id": task.id,
            "moderation_version": task.moderation_version,
            "attempt": task.attempt_count + 1,
        },
    )
    monitor.start(
        input_value={
            "content_type": task.content_type,
            "content_id": task.content_id,
            "content": content,
        }
    )
    monitor.record_event(
        event_type="content.loaded",
        component_type="data",
        component_name=task.content_type,
        status="SUCCEEDED",
        payload={"content_id": task.content_id, "user_id": user_id},
    )

    try:
        with bind_monitor(monitor):
            decision, usage = await evaluate_content(
                content_type=task.content_type,
                content=content,
            )
            async with AsyncSessionLocal() as db:
                applied = await apply_moderation_decision(
                    db,
                    task=task,
                    decision=decision,
                    agent_run_id=monitor.run_id,
                )
        monitor.record_event(
            event_type="moderation.applied",
            component_type="business",
            component_name=task.content_type,
            status="SUCCEEDED" if applied else "CANCELLED",
            payload={
                "content_id": task.content_id,
                "applied": applied,
                **decision.model_dump(),
            },
        )
        monitor.complete(
            output_value={"applied": applied, **decision.model_dump()},
            usage=usage,
        )
    except asyncio.CancelledError:
        monitor.cancel()
        raise
    except Exception as exc:
        monitor.record_event(
            event_type="moderation.failed",
            component_type="workflow",
            component_name="content_moderation",
            status="FAILED",
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        monitor.fail(exc)
        async with AsyncSessionLocal() as db:
            await mark_moderation_attempt_failed(
                db,
                task_id=task.id,
                error=exc,
                agent_run_id=monitor.run_id,
            )


async def _worker_loop() -> None:
    """持续领取并处理审核任务。"""
    while True:
        try:
            async with AsyncSessionLocal() as db:
                tasks = await claim_pending_tasks(
                    db,
                    limit=settings.content_moderation_batch_size,
                    lease_seconds=settings.content_moderation_lease_seconds,
                )
            if not tasks:
                await asyncio.sleep(settings.content_moderation_poll_seconds)
                continue
            await asyncio.gather(
                *(process_moderation_task(task) for task in tasks),
                return_exceptions=False,
            )
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Content moderation worker iteration failed")
            await asyncio.sleep(settings.content_moderation_poll_seconds)


def setup_content_moderation_worker() -> asyncio.Task[None]:
    """启动进程内审核 Worker。"""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(
            _worker_loop(), name="content-moderation-worker"
        )
    return _worker_task


async def close_content_moderation_worker() -> None:
    """停止审核 Worker。"""
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    await asyncio.gather(_worker_task, return_exceptions=True)
    _worker_task = None
