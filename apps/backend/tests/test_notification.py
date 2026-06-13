"""通知模块测试，覆盖通知触发、幂等、列表、未读统计与已读标记。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.comment import Comment
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.models.notification import Notification
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/notifications"


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash("secret"),
        nickname=username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_space_post(db: AsyncSession, user_id: int) -> SpacePost:
    post = SpacePost(user_id=user_id, content="hello", post_type="original")
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def test_follow_creates_notification(
    client: TestClient, db_session: AsyncSession
):
    """关注他人时，被关注者应收到一条 FOLLOW 通知。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    resp = client.post(
        "/api/v1/users/follow",
        json={"followee_id": bob.id},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 204

    notifications = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == bob.id)
        )
    ).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].type == int(NotificationType.FOLLOW)
    assert notifications[0].actor_id == alice.id


async def test_follow_notification_is_idempotent(
    client: TestClient, db_session: AsyncSession
):
    """重复触发同类未读通知不会再次入库。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    client.post(
        "/api/v1/users/follow",
        json={"followee_id": bob.id},
        headers=_auth_header(alice),
    )
    # 取关后再次关注，由于第一条通知仍未读，幂等约束阻止再次插入
    client.post(
        "/api/v1/users/unfollow",
        json={"followee_id": bob.id},
        headers=_auth_header(alice),
    )
    client.post(
        "/api/v1/users/follow",
        json={"followee_id": bob.id},
        headers=_auth_header(alice),
    )
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == bob.id)
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_self_follow_blocked_no_notification(
    client: TestClient, db_session: AsyncSession
):
    """自己关注自己被拒绝且不产生通知。"""
    alice = await _create_user(db_session, "alice")
    resp = client.post(
        "/api/v1/users/follow",
        json={"followee_id": alice.id},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 400
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalars().all()
    assert rows == []


async def test_space_post_like_triggers_notification(
    client: TestClient, db_session: AsyncSession
):
    """点赞他人空间动态会触发通知，自赞不触发。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    post = await _create_space_post(db_session, alice.id)

    client.post(
        f"/api/v1/space-posts/{post.id}/like",
        headers=_auth_header(bob),
    )
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].type == int(NotificationType.SPACE_POST_LIKE)

    # 自赞不产生通知
    client.post(
        f"/api/v1/space-posts/{post.id}/like",
        headers=_auth_header(alice),
    )
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_comment_reply_triggers_notification(
    client: TestClient, db_session: AsyncSession
):
    """回复他人评论会触发 COMMENT_REPLY 通知。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    post = await _create_space_post(db_session, alice.id)

    # alice 在自己的动态下评论一条，不应产生通知
    resp = client.post(
        "/api/v1/comments/",
        json={
            "target_type": "space_post",
            "target_id": post.id,
            "content": "first comment",
        },
        headers=_auth_header(alice),
    )
    parent_id = resp.json()["id"]
    rows = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalars().all()
    assert rows == []

    # bob 回复 alice 的评论：应触发 COMMENT_REPLY 通知给 alice
    client.post(
        "/api/v1/comments/",
        json={
            "target_type": "space_post",
            "target_id": post.id,
            "content": "reply",
            "parent_id": parent_id,
        },
        headers=_auth_header(bob),
    )
    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.recipient_id == alice.id,
                Notification.type == int(NotificationType.COMMENT_REPLY),
            )
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_unread_summary_and_mark_all_read(
    client: TestClient, db_session: AsyncSession
):
    """未读汇总应统计通知数，read-all 后归零。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    client.post(
        "/api/v1/users/follow",
        json={"followee_id": alice.id},
        headers=_auth_header(bob),
    )
    summary = client.get(
        f"{BASE_URL}/unread-summary", headers=_auth_header(alice)
    ).json()
    assert summary["notification_unread"] == 1
    assert summary["message_unread"] == 0

    resp = client.post(f"{BASE_URL}/read-all", headers=_auth_header(alice))
    assert resp.status_code == 204
    summary = client.get(
        f"{BASE_URL}/unread-summary", headers=_auth_header(alice)
    ).json()
    assert summary["notification_unread"] == 0


async def test_list_notifications_pagination(
    client: TestClient, db_session: AsyncSession
):
    """通知列表按时间倒序分页返回。"""
    alice = await _create_user(db_session, "alice")
    for i in range(3):
        u = await _create_user(db_session, f"user{i}")
        client.post(
            "/api/v1/users/follow",
            json={"followee_id": alice.id},
            headers=_auth_header(u),
        )
    body = client.get(
        f"{BASE_URL}/?limit=2&offset=0", headers=_auth_header(alice)
    ).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


async def test_mark_single_notification_read(
    client: TestClient, db_session: AsyncSession
):
    """标记单条通知已读。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    client.post(
        "/api/v1/users/follow",
        json={"followee_id": alice.id},
        headers=_auth_header(bob),
    )
    notif = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalar_one()

    resp = client.post(
        f"{BASE_URL}/{notif.id}/read", headers=_auth_header(alice)
    )
    assert resp.status_code == 204
    summary = client.get(
        f"{BASE_URL}/unread-summary", headers=_auth_header(alice)
    ).json()
    assert summary["notification_unread"] == 0


async def test_mark_other_user_notification_forbidden(
    client: TestClient, db_session: AsyncSession
):
    """不能标记别人的通知为已读。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    eve = await _create_user(db_session, "eve")
    client.post(
        "/api/v1/users/follow",
        json={"followee_id": alice.id},
        headers=_auth_header(bob),
    )
    notif = (
        await db_session.execute(
            select(Notification).where(Notification.recipient_id == alice.id)
        )
    ).scalar_one()
    resp = client.post(
        f"{BASE_URL}/{notif.id}/read", headers=_auth_header(eve)
    )
    assert resp.status_code == 404
