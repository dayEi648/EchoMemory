"""内容审核服务测试。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient

from echomemory_backend.core.security.security import (
    create_access_token,
    get_password_hash,
)
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.content_moderation import (
    ContentModerationTask,
    UserContentModerationStats,
)
from echomemory_backend.models.music import Music
from echomemory_backend.models.user import User
from echomemory_backend.models.enums import UserRole
from tests.api_helpers import api_data
from echomemory_backend.schemas.content_moderation import ModerationDecision
from echomemory_backend.services.content_moderation_service import (
    apply_moderation_decision,
    claim_pending_tasks,
    classify_recommendation_score,
    classify_safety_score,
    enqueue_moderation,
    mark_moderation_attempt_failed,
)
from echomemory_backend.ai.clients.deepseek import ChatResponse
from echomemory_backend.ai.graphs.content_moderation import workflow
from echomemory_backend.ai.monitoring.context import AgentMonitorSession
from echomemory_backend.ai.monitoring.runtime import bind_monitor


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        nickname=username,
        password_hash=get_password_hash("secret"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_comment(db: AsyncSession, user_id: int) -> Comment:
    music = Music(
        title="Moderation song",
        is_published=True,
        file_url="https://example.com/song.mp3",
    )
    db.add(music)
    await db.flush()
    comment = Comment(
        user_id=user_id,
        music_id=music.id,
        content="content to review",
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


def test_score_classification_uses_confirmed_thresholds():
    assert classify_safety_score(3) == "DANGEROUS"
    assert classify_safety_score(4) == "RISKY"
    assert classify_safety_score(7) == "SAFE"
    assert classify_recommendation_score(7) == "NORMAL"
    assert classify_recommendation_score(8) == "RECOMMENDED"


async def test_moderation_agent_validates_output_and_records_flow(monkeypatch):
    class RecordingWriter:
        def __init__(self):
            self.operations = []

        def enqueue(self, operation):
            self.operations.append(operation)
            return True

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def chat(self, messages, **kwargs):
            return ChatResponse(
                content=(
                    '{"safety_score": 8, "recommendation_score": 9, '
                    '"reason": "内容友善且有价值"}'
                ),
                model="fake-model",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
            )

    monkeypatch.setattr(workflow, "DeepSeekClient", FakeClient)
    writer = RecordingWriter()
    monitor = AgentMonitorSession(
        writer=writer,
        scenario="content_moderation",
        workflow_type="workflow",
        workflow_name="content_moderation",
    )
    monitor.start(input_value={"content": "test"})

    with bind_monitor(monitor):
        decision, usage = await workflow.evaluate_content(
            content_type="comment",
            content="一条友善的音乐评论",
        )
    monitor.complete(output_value=decision.model_dump(), usage=usage)

    event_types = [
        operation.values["event_type"]
        for operation in writer.operations
        if operation.kind == "create_event"
    ]
    assert decision.safety_score == 8
    assert decision.recommendation_score == 9
    assert event_types == [
        "prompt.rendered",
        "llm.started",
        "llm.completed",
        "output.validated",
    ]


async def test_enqueue_moderation_creates_one_pending_task(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "queue_user")
    comment = await _create_comment(db_session, user.id)

    await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )
    await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )

    tasks = list(
        (
            await db_session.execute(
                select(ContentModerationTask).where(
                    ContentModerationTask.content_type == "comment",
                    ContentModerationTask.content_id == comment.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(tasks) == 1
    assert tasks[0].status == "PENDING"


async def test_claim_pending_task_marks_it_processing(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "claim_user")
    comment = await _create_comment(db_session, user.id)
    await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )

    claimed = await claim_pending_tasks(db_session, limit=1)

    assert len(claimed) == 1
    assert claimed[0].status == "PROCESSING"
    assert claimed[0].locked_at is not None


async def test_dangerous_result_deletes_content_and_updates_stats(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "danger_user")
    comment = await _create_comment(db_session, user.id)
    task = await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )

    await apply_moderation_decision(
        db_session,
        task=task,
        decision=ModerationDecision(
            safety_score=2,
            recommendation_score=9,
            reason="包含危险内容",
        ),
    )

    await db_session.refresh(comment)
    stats = await db_session.get(UserContentModerationStats, user.id)
    assert comment.is_deleted is True
    assert comment.deletion_reason == "MODERATION_DANGEROUS"
    assert comment.safety_level == "DANGEROUS"
    assert comment.is_recommended is True
    assert stats is not None
    assert stats.dangerous_count == 1
    assert stats.recommended_count == 1


async def test_moderation_never_turns_user_deletion_into_restorable_deletion(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "self_deleted_content_user")
    comment = await _create_comment(db_session, user.id)
    task = await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )
    comment.is_deleted = True
    comment.deletion_reason = "USER"
    await db_session.commit()

    await apply_moderation_decision(
        db_session,
        task=task,
        decision=ModerationDecision(
            safety_score=1,
            recommendation_score=0,
            reason="危险内容",
        ),
    )

    await db_session.refresh(comment)
    assert comment.is_deleted is True
    assert comment.deletion_reason == "USER"


async def test_new_effective_result_replaces_previous_stats(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "replace_user")
    comment = await _create_comment(db_session, user.id)
    first_task = await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )
    await apply_moderation_decision(
        db_session,
        task=first_task,
        decision=ModerationDecision(
            safety_score=5,
            recommendation_score=4,
            reason="存在一定风险",
        ),
    )

    second_task = await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        force=True,
        commit=True,
    )
    await apply_moderation_decision(
        db_session,
        task=second_task,
        decision=ModerationDecision(
            safety_score=9,
            recommendation_score=9,
            reason="人工确认安全且值得推荐",
        ),
        source="MANUAL",
    )

    stats = await db_session.get(UserContentModerationStats, user.id)
    assert stats is not None
    assert stats.risky_count == 0
    assert stats.dangerous_count == 0
    assert stats.recommended_count == 1


async def test_third_failure_hides_content_and_marks_failed(
    db_session: AsyncSession,
):
    user = await _create_user(db_session, "failed_user")
    comment = await _create_comment(db_session, user.id)
    task = await enqueue_moderation(
        db_session,
        content_type="comment",
        content_id=comment.id,
        commit=True,
    )

    for attempt in range(3):
        terminal = await mark_moderation_attempt_failed(
            db_session,
            task_id=task.id,
            error=RuntimeError(f"attempt {attempt + 1}"),
        )

    await db_session.refresh(comment)
    await db_session.refresh(task)
    assert terminal is True
    assert task.status == "FAILED"
    assert task.attempt_count == 3
    assert comment.is_deleted is True
    assert comment.deletion_reason == "MODERATION_FAILED"
    assert comment.moderation_status == "FAILED"


async def test_admin_can_filter_comments_and_apply_manual_review(
    client: TestClient,
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "moderation_admin")
    admin.role = UserRole.ADMIN
    author = await _create_user(db_session, "moderation_author")
    comment = await _create_comment(db_session, author.id)
    await db_session.commit()

    list_response = client.get(
        "/api/v1/admin/content-moderation/comments",
        headers=_auth_header(admin),
        params={"moderation_status": "PENDING", "q": "content"},
    )
    assert list_response.status_code == 200
    assert api_data(list_response)["total"] == 1

    review_response = client.post(
        f"/api/v1/admin/content-moderation/comments/{comment.id}/manual-review",
        headers=_auth_header(admin),
        json={
            "safety_score": 8,
            "recommendation_score": 9,
            "reason": "管理员复核通过",
        },
    )
    assert review_response.status_code == 200
    reviewed = api_data(review_response)
    assert reviewed["moderation_status"] == "MANUAL"
    assert reviewed["safety_level"] == "SAFE"
    assert reviewed["is_recommended"] is True

    stats_response = client.get(
        f"/api/v1/admin/content-moderation/users/{author.id}/stats",
        headers=_auth_header(admin),
    )
    assert stats_response.status_code == 200
    stats = api_data(stats_response)
    assert stats["dangerous_count"] == 0
    assert stats["risky_count"] == 0
    assert stats["recommended_count"] == 1


async def test_admin_can_restore_moderation_deleted_comment(
    client: TestClient,
    db_session: AsyncSession,
):
    admin = await _create_user(db_session, "restore_admin")
    admin.role = UserRole.ADMIN
    author = await _create_user(db_session, "restore_author")
    comment = await _create_comment(db_session, author.id)
    comment.is_deleted = True
    comment.deletion_reason = "MODERATION_DANGEROUS"
    await db_session.commit()

    response = client.post(
        f"/api/v1/admin/content-moderation/comments/{comment.id}/restore",
        headers=_auth_header(admin),
    )

    assert response.status_code == 200
    restored = api_data(response)
    assert restored["is_deleted"] is False
    assert restored["deletion_reason"] is None
