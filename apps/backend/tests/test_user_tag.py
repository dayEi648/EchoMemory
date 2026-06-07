from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.user import User
from echomemory_backend.models.user_tag import UserEmotionTag, UserInterestTag

BASE = "/api/v1/users"
EMOTION_TAGS_URL = f"{BASE}/me/emotion-tags"
INTEREST_TAGS_URL = f"{BASE}/me/interest-tags"


async def _create_user(db: AsyncSession, username: str, password: str = "secret") -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=username.capitalize(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


class TestEmotionTags:
    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "empty_emotion")
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "emotion_user")
        db_session.add(UserEmotionTag(user_id=user.id, emotion_tag_id=1))
        db_session.add(UserEmotionTag(user_id=user.id, emotion_tag_id=2))
        await db_session.commit()

        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}
        names = {item["name"] for item in data}
        assert names == {"治愈", "激昂"}

    async def test_unauthorized(self, client: TestClient):
        resp = client.get(EMOTION_TAGS_URL)
        assert resp.status_code == 401


class TestInterestTags:
    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "empty_interest")
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "interest_user")
        db_session.add(UserInterestTag(user_id=user.id, interest_tag_id=1))
        db_session.add(UserInterestTag(user_id=user.id, interest_tag_id=2))
        await db_session.commit()

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}
        names = {item["name"] for item in data}
        assert names == {"运动", "学习"}

    async def test_unauthorized(self, client: TestClient):
        resp = client.get(INTEREST_TAGS_URL)
        assert resp.status_code == 401
