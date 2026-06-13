"""私信模块测试：会话、发送、屏蔽、未读统计。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.message import Conversation, DirectMessage, UserBlock
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/messages"


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


async def test_send_message_creates_conversation_and_message(
    client: TestClient, db_session: AsyncSession
):
    """首次发送消息会创建会话与消息记录。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    resp = client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "hello"},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["content"] == "hello"
    assert body["sender_id"] == alice.id

    convs = (
        await db_session.execute(select(Conversation))
    ).scalars().all()
    assert len(convs) == 1
    msgs = (
        await db_session.execute(select(DirectMessage))
    ).scalars().all()
    assert len(msgs) == 1


async def test_send_message_to_self_rejected(
    client: TestClient, db_session: AsyncSession
):
    """禁止给自己发私信。"""
    alice = await _create_user(db_session, "alice")
    resp = client.post(
        f"{BASE_URL}/{alice.id}",
        json={"content": "self"},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 400


async def test_send_message_blocked_returns_403(
    client: TestClient, db_session: AsyncSession
):
    """被对方屏蔽后无法再发送私信。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    # bob 屏蔽 alice
    resp = client.post(
        f"/api/v1/users/{alice.id}/block", headers=_auth_header(bob)
    )
    assert resp.status_code == 204

    resp = client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "spam"},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 403


async def test_unblock_restores_send_capability(
    client: TestClient, db_session: AsyncSession
):
    """取消屏蔽后可恢复发送。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    client.post(f"/api/v1/users/{alice.id}/block", headers=_auth_header(bob))
    client.delete(f"/api/v1/users/{alice.id}/block", headers=_auth_header(bob))

    resp = client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "hi again"},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 201


async def test_unread_count_and_mark_read(
    client: TestClient, db_session: AsyncSession
):
    """对方发送消息后接收方未读数+1，标记已读后归零。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")

    client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "1"},
        headers=_auth_header(alice),
    )
    client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "2"},
        headers=_auth_header(alice),
    )

    summary = client.get(
        "/api/v1/notifications/unread-summary", headers=_auth_header(bob)
    ).json()
    assert summary["message_unread"] == 2

    convs = client.get(
        f"{BASE_URL}/conversations", headers=_auth_header(bob)
    ).json()
    assert convs["total"] == 1
    conv_id = convs["items"][0]["id"]
    assert convs["items"][0]["unread_count"] == 2

    resp = client.post(
        f"{BASE_URL}/conversations/{conv_id}/read", headers=_auth_header(bob)
    )
    assert resp.status_code == 204

    summary = client.get(
        "/api/v1/notifications/unread-summary", headers=_auth_header(bob)
    ).json()
    assert summary["message_unread"] == 0


async def test_list_messages_returns_desc_order(
    client: TestClient, db_session: AsyncSession
):
    """会话内消息按时间倒序返回。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    for i in range(3):
        client.post(
            f"{BASE_URL}/{bob.id}",
            json={"content": f"msg{i}"},
            headers=_auth_header(alice),
        )

    convs = client.get(
        f"{BASE_URL}/conversations", headers=_auth_header(alice)
    ).json()
    conv_id = convs["items"][0]["id"]

    body = client.get(
        f"{BASE_URL}/conversations/{conv_id}/messages",
        headers=_auth_header(alice),
    ).json()
    assert body["total"] == 3
    assert [m["content"] for m in body["items"]] == ["msg2", "msg1", "msg0"]


async def test_get_conversation_with_user_404_when_no_history(
    client: TestClient, db_session: AsyncSession
):
    """与某用户无任何会话时获取元数据返回 404。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    resp = client.get(
        f"{BASE_URL}/conversations/with/{bob.id}",
        headers=_auth_header(alice),
    )
    assert resp.status_code == 404


async def test_list_messages_for_other_user_conversation_forbidden(
    client: TestClient, db_session: AsyncSession
):
    """非会话参与者无法拉取消息。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    eve = await _create_user(db_session, "eve")

    client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "secret"},
        headers=_auth_header(alice),
    )
    convs = client.get(
        f"{BASE_URL}/conversations", headers=_auth_header(alice)
    ).json()
    conv_id = convs["items"][0]["id"]

    resp = client.get(
        f"{BASE_URL}/conversations/{conv_id}/messages",
        headers=_auth_header(eve),
    )
    assert resp.status_code == 404


async def test_block_self_rejected(
    client: TestClient, db_session: AsyncSession
):
    """禁止屏蔽自己。"""
    alice = await _create_user(db_session, "alice")
    resp = client.post(
        f"/api/v1/users/{alice.id}/block", headers=_auth_header(alice)
    )
    assert resp.status_code == 400


async def test_message_content_too_long_rejected(
    client: TestClient, db_session: AsyncSession
):
    """超长消息返回 422。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    resp = client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "x" * 3000},
        headers=_auth_header(alice),
    )
    assert resp.status_code == 422


async def test_block_does_not_remove_existing_conversation(
    client: TestClient, db_session: AsyncSession
):
    """屏蔽前已存在的消息历史不会被删除。"""
    alice = await _create_user(db_session, "alice")
    bob = await _create_user(db_session, "bob")
    client.post(
        f"{BASE_URL}/{bob.id}",
        json={"content": "before block"},
        headers=_auth_header(alice),
    )
    client.post(f"/api/v1/users/{alice.id}/block", headers=_auth_header(bob))

    convs = (
        await db_session.execute(select(Conversation))
    ).scalars().all()
    assert len(convs) == 1
    blocks = (
        await db_session.execute(select(UserBlock))
    ).scalars().all()
    assert len(blocks) == 1
