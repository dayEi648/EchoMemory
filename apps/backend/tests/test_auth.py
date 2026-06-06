import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core import redis_client as rc
from echomemory_backend.core.security import decode_access_token
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


async def _create_user_directly(db: AsyncSession, username: str = "tester", password: str = "secret123") -> User:
    from echomemory_backend.core.security import get_password_hash

    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname="Tester",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestRegister:
    async def test_register_success(self, client: TestClient):
        resp = client.post(
            REGISTER_URL,
            json={"username": "alice", "password": "secret123", "nickname": "Alice"},
        )
        assert resp.status_code == 201
        data = resp.json()

        # Both tokens returned
        assert "access_token" in data
        assert "refresh_token" in data
        assert decode_access_token(data["access_token"]) is not None

        # Verify user was created by calling /me
        me_resp = client.get(
            ME_URL, headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == "alice"
        assert me_data["nickname"] == "Alice"
        assert "id" in me_data
        assert me_data["role"] == UserRole.USER.value

    async def test_register_duplicate_username(self, client: TestClient):
        client.post(
            REGISTER_URL,
            json={"username": "bob", "password": "secret123", "nickname": "Bob"},
        )
        resp = client.post(
            REGISTER_URL,
            json={"username": "bob", "password": "secret123", "nickname": "Bob2"},
        )
        assert resp.status_code == 409

    async def test_register_duplicate_email(self, client: TestClient):
        client.post(
            REGISTER_URL,
            json={
                "username": "carol",
                "password": "secret123",
                "nickname": "Carol",
                "email": "carol@example.com",
            },
        )
        resp = client.post(
            REGISTER_URL,
            json={
                "username": "carol2",
                "password": "secret123",
                "nickname": "Carol2",
                "email": "carol@example.com",
            },
        )
        assert resp.status_code == 409

    async def test_register_validation_short_password(self, client: TestClient):
        resp = client.post(
            REGISTER_URL,
            json={"username": "dave", "password": "123", "nickname": "Dave"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: TestClient, db_session: AsyncSession):
        await _create_user_directly(db_session, username="login_user", password="mypassword")
        resp = client.post(
            LOGIN_URL,
            json={"username": "login_user", "password": "mypassword"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: TestClient, db_session: AsyncSession):
        await _create_user_directly(db_session, username="login_user2", password="mypassword")
        resp = client.post(
            LOGIN_URL,
            json={"username": "login_user2", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_deleted_user(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user_directly(db_session, username="deleted", password="secret")
        user.is_deleted = True
        await db_session.commit()
        resp = client.post(
            LOGIN_URL,
            json={"username": "deleted", "password": "secret"},
        )
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user_directly(db_session, username="refresh_user", password="secret")
        await rc.store_refresh_token("valid_rt", user.id)

        resp = client.post(REFRESH_URL, json={"refresh_token": "valid_rt"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

        # Old refresh token should be rotated (deleted)
        assert await rc.get_refresh_token_user_id("valid_rt") is None

    async def test_refresh_invalid_token(self, client: TestClient):
        resp = client.post(REFRESH_URL, json={"refresh_token": "bogus"})
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_success(self, client: TestClient, db_session: AsyncSession):
        from echomemory_backend.core.security import create_access_token

        user = await _create_user_directly(db_session, username="logout_user", password="secret")
        await rc.store_refresh_token("logout_rt", user.id)
        token = create_access_token(subject=user.id)

        resp = client.post(
            LOGOUT_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": "logout_rt"},
        )
        assert resp.status_code == 204

        assert await rc.get_refresh_token_user_id("logout_rt") is None
        assert await rc.is_access_token_blacklisted(token) is True


class TestGetMe:
    async def test_get_me_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user_directly(db_session, username="me_user", password="secret")
        from echomemory_backend.core.security import create_access_token

        token = create_access_token(subject=user.id)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "me_user"
        assert data["id"] == user.id

    async def test_get_me_no_token(self, client: TestClient):
        resp = client.get(ME_URL)
        assert resp.status_code == 401  # OAuth2 returns 401 when token is missing

    async def test_get_me_banned_user(self, client: TestClient, db_session: AsyncSession):
        from sqlalchemy import func

        user = await _create_user_directly(db_session, username="banned", password="secret")
        user.status = UserStatus.BANNED.value
        user.banned_at = func.now()
        await db_session.commit()
        from echomemory_backend.core.security import create_access_token

        token = create_access_token(subject=user.id)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_get_me_blacklisted_token(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user_directly(db_session, username="blacklisted", password="secret")
        from echomemory_backend.core.security import create_access_token

        token = create_access_token(subject=user.id)
        await rc.blacklist_access_token(token)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
