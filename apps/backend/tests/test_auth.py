from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.clients import redis_client as rc
from echomemory_backend.core.security.security import decode_access_token
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.user import User
from echomemory_backend.services.playlist_service import DEFAULT_LIKE_PLAYLIST_TITLE
from tests.api_helpers import api_data

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"


async def _create_user_directly(db: AsyncSession, username: str = "tester", password: str = "secret123") -> User:
    from echomemory_backend.core.security.security import get_password_hash

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
    """测试用户注册相关接口。"""

    async def test_register_success(self, client: TestClient):
        """测试正常注册用户，验证返回双令牌及用户信息。"""
        resp = client.post(
            REGISTER_URL,
            data={"username": "alice", "password": "secret123", "nickname": "Alice"},
        )
        assert resp.status_code == 201
        data = api_data(resp)

        # Both tokens returned
        assert "access_token" in data
        assert "refresh_token" in data
        assert decode_access_token(data["access_token"]) is not None

        # Verify user was created by calling /me
        me_resp = client.get(
            ME_URL, headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        assert me_resp.status_code == 200
        me_data = api_data(me_resp)
        assert me_data["username"] == "alice"
        assert me_data["nickname"] == "Alice"
        assert "id" in me_data
        assert me_data["role"] == UserRole.USER.value

    async def test_register_creates_default_like_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试注册成功后自动创建「我喜欢的音乐」私密系统歌单。"""
        resp = client.post(
            REGISTER_URL,
            data={"username": "like_pl_user", "password": "secret123", "nickname": "Like"},
        )
        assert resp.status_code == 201
        me_data = api_data(
            client.get(
                ME_URL,
                headers={"Authorization": f"Bearer {api_data(resp)['access_token']}"},
            )
        )

        stmt = select(Playlist).where(
            Playlist.user_id == me_data["id"],
            Playlist.is_like.is_(True),
        )
        playlist = (await db_session.execute(stmt)).scalar_one()
        assert playlist.title == DEFAULT_LIKE_PLAYLIST_TITLE
        assert playlist.is_private is True

    async def test_register_duplicate_username(self, client: TestClient):
        """测试注册时用户名已存在，返回 409。"""
        client.post(
            REGISTER_URL,
            data={"username": "bob", "password": "secret123", "nickname": "Bob"},
        )
        resp = client.post(
            REGISTER_URL,
            data={"username": "bob", "password": "secret123", "nickname": "Bob2"},
        )
        assert resp.status_code == 409

    async def test_register_duplicate_email(self, client: TestClient):
        """测试注册时邮箱已存在，返回 409。"""
        client.post(
            REGISTER_URL,
            data={
                "username": "carol",
                "password": "secret123",
                "nickname": "Carol",
                "email": "carol@example.com",
            },
        )
        resp = client.post(
            REGISTER_URL,
            data={
                "username": "carol2",
                "password": "secret123",
                "nickname": "Carol2",
                "email": "carol@example.com",
            },
        )
        assert resp.status_code == 409

    async def test_register_validation_short_password(self, client: TestClient):
        """测试注册时密码过短，返回 422。"""
        resp = client.post(
            REGISTER_URL,
            data={"username": "dave", "password": "123", "nickname": "Dave"},
        )
        assert resp.status_code == 422


class TestLogin:
    """测试用户登录相关接口。"""

    async def test_login_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常登录，验证返回双令牌。"""
        await _create_user_directly(db_session, username="login_user", password="mypassword")
        resp = client.post(
            LOGIN_URL,
            json={"username": "login_user", "password": "mypassword"},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: TestClient, db_session: AsyncSession):
        """测试密码错误时返回 401。"""
        await _create_user_directly(db_session, username="login_user2", password="mypassword")
        resp = client.post(
            LOGIN_URL,
            json={"username": "login_user2", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    async def test_login_deleted_user(self, client: TestClient, db_session: AsyncSession):
        """测试已删除用户登录时返回 401。"""
        user = await _create_user_directly(db_session, username="deleted", password="secret")
        user.is_deleted = True
        await db_session.commit()
        resp = client.post(
            LOGIN_URL,
            json={"username": "deleted", "password": "secret"},
        )
        assert resp.status_code == 401

    async def test_login_banned_user_returns_403(
        self, client: TestClient, db_session: AsyncSession
    ):
        """认证通过但账号被永久封禁时返回 403。"""
        user = await _create_user_directly(db_session, username="banned_login", password="secret")
        user.status = UserStatus.BANNED.value
        user.banned_at = func.now()
        await db_session.commit()

        resp = client.post(
            LOGIN_URL,
            json={"username": "banned_login", "password": "secret"},
        )
        assert resp.status_code == 403

    async def test_login_writes_last_login_at(self, client: TestClient, db_session: AsyncSession):
        """测试登录成功后写入 last_login_at。"""
        user = await _create_user_directly(db_session, username="lastlogin", password="secret")
        assert user.last_login_at is None

        resp = client.post(
            LOGIN_URL,
            json={"username": "lastlogin", "password": "secret"},
        )
        assert resp.status_code == 200

        await db_session.refresh(user)
        assert user.last_login_at is not None


class TestRefresh:
    """测试令牌刷新相关接口。"""

    async def test_refresh_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常刷新令牌，验证旧 refresh token 被轮换。"""
        user = await _create_user_directly(db_session, username="refresh_user", password="secret")
        await rc.store_refresh_token("valid_rt", user.id, version=0)

        resp = client.post(REFRESH_URL, json={"refresh_token": "valid_rt"})
        assert resp.status_code == 200
        data = api_data(resp)
        assert "access_token" in data
        assert "refresh_token" in data

        # Old refresh token should be rotated (deleted)
        assert await rc.get_refresh_token_user_id("valid_rt") is None

    async def test_refresh_invalid_token(self, client: TestClient):
        """测试无效的 refresh token 返回 401。"""
        resp = client.post(REFRESH_URL, json={"refresh_token": "bogus"})
        assert resp.status_code == 401

    async def test_refresh_version_mismatch(self, client: TestClient, db_session: AsyncSession):
        """测试 refresh token 版本不匹配时返回 401。"""
        user = await _create_user_directly(db_session, username="refresh_version", password="secret")
        await rc.store_refresh_token("old_rt", user.id, version=0)
        await rc.increment_user_token_version(user.id)

        resp = client.post(REFRESH_URL, json={"refresh_token": "old_rt"})
        assert resp.status_code == 401


class TestLogout:
    """测试用户登出相关接口。"""

    async def test_logout_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常登出，验证令牌被加入黑名单。"""
        from echomemory_backend.core.security.security import create_access_token

        user = await _create_user_directly(db_session, username="logout_user", password="secret")
        await rc.store_refresh_token("logout_rt", user.id, version=0)
        token = create_access_token(subject=user.id, version=0)

        resp = client.post(
            LOGOUT_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": "logout_rt"},
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        assert await rc.get_refresh_token_user_id("logout_rt") is None
        assert await rc.is_access_token_blacklisted(token) is True
        assert await rc.is_refresh_token_blacklisted("logout_rt") is True

    async def test_logout_only_revokes_current_device(self, client: TestClient, db_session: AsyncSession):
        """主动登出只吊销当前设备 token，不递增全局 token version。"""
        from echomemory_backend.core.security.security import create_access_token

        user = await _create_user_directly(db_session, username="logout_version", password="secret")
        await rc.store_refresh_token("logout_rt2", user.id, version=0)
        await rc.store_refresh_token("other_rt", user.id, version=0)
        token = create_access_token(
            subject=user.id, version=0, expires_delta=timedelta(minutes=10)
        )
        other_token = create_access_token(
            subject=user.id, version=0, expires_delta=timedelta(minutes=11)
        )

        resp = client.post(
            LOGOUT_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"refresh_token": "logout_rt2"},
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        # 当前 access token 被加入黑名单
        me_resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 401

        # 其他设备 access/refresh token 仍有效
        other_me_resp = client.get(ME_URL, headers={"Authorization": f"Bearer {other_token}"})
        assert other_me_resp.status_code == 200
        other_refresh_resp = client.post(REFRESH_URL, json={"refresh_token": "other_rt"})
        assert other_refresh_resp.status_code == 200

        refresh_resp = client.post(REFRESH_URL, json={"refresh_token": "logout_rt2"})
        assert refresh_resp.status_code == 401


class TestGetMe:
    """测试获取当前用户信息相关接口。"""

    async def test_get_me_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常获取当前用户信息。"""
        user = await _create_user_directly(db_session, username="me_user", password="secret")
        from echomemory_backend.core.security.security import create_access_token

        token = create_access_token(subject=user.id, version=0)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["username"] == "me_user"
        assert data["id"] == user.id

    async def test_get_me_no_token(self, client: TestClient):
        """测试未携带令牌时返回 401。"""
        resp = client.get(ME_URL)
        assert resp.status_code == 401  # OAuth2 returns 401 when token is missing

    async def test_get_me_banned_user(self, client: TestClient, db_session: AsyncSession):
        """测试被封禁用户访问时返回 403。"""
        from sqlalchemy import func

        user = await _create_user_directly(db_session, username="banned", password="secret")
        user.status = UserStatus.BANNED.value
        user.banned_at = func.now()
        await db_session.commit()
        from echomemory_backend.core.security.security import create_access_token

        token = create_access_token(subject=user.id, version=0)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_get_me_blacklisted_token(self, client: TestClient, db_session: AsyncSession):
        """测试黑名单中的令牌返回 401。"""
        user = await _create_user_directly(db_session, username="blacklisted", password="secret")
        from echomemory_backend.core.security.security import create_access_token

        token = create_access_token(subject=user.id, version=0)
        await rc.blacklist_access_token(token)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    async def test_get_me_version_mismatch(self, client: TestClient, db_session: AsyncSession):
        """测试令牌版本不匹配时返回 401。"""
        user = await _create_user_directly(db_session, username="versioned", password="secret")
        from echomemory_backend.core.security.security import create_access_token

        # 模拟 version 已被递增（如 logout / ban 后）
        await rc.increment_user_token_version(user.id)
        token = create_access_token(subject=user.id, version=0)
        resp = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
