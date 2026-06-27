import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.notification import Notification
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.user import User, UserFollow
from tests.api_helpers import api_data

BASE = "/api/v1/users"
ME_URL = f"{BASE}/me"
SEARCH_URL = f"{BASE}/"
FOLLOW_URL = f"{BASE}/follow"
UNFOLLOW_URL = f"{BASE}/unfollow"
ADMIN_LIST_URL = f"{BASE}/admin/list"
ADMIN_CREATE_URL = f"{BASE}/admin/create"


def _make_image_bytes() -> bytes:
    """Generate a tiny valid JPEG image in memory."""
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _create_user(db: AsyncSession, username: str, password: str = "secret", role: int = UserRole.USER.value, status: int = UserStatus.ACTIVE.value, **kwargs) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=kwargs.get("nickname", username.capitalize()),
        email=kwargs.get("email"),
        role=role,
        status=status,
        **{k: v for k, v in kwargs.items() if k not in ("nickname", "email")},
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


class TestUpdateMe:
    """测试当前用户资料更新相关功能。"""

    async def test_update_nickname(self, client: TestClient, db_session: AsyncSession):
        """测试正常更新昵称。"""
        user = await _create_user(db_session, "updater")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            data={"nickname": "NewName"},
        )
        assert resp.status_code == 200
        assert api_data(resp)["nickname"] == "NewName"

    async def test_update_email_conflict(self, client: TestClient, db_session: AsyncSession):
        """测试更新邮箱时与已有邮箱冲突返回 409。"""
        await _create_user(db_session, "email_owner", email="taken@example.com")
        user = await _create_user(db_session, "updater2")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            data={"email": "taken@example.com"},
        )
        assert resp.status_code == 409

    async def test_update_unauthorized(self, client: TestClient):
        """测试未登录时更新资料返回 401。"""
        resp = client.patch(ME_URL, data={"nickname": "x"})
        assert resp.status_code == 401

    async def test_update_avatar(self, client: TestClient, db_session: AsyncSession, monkeypatch):
        """测试正常更新头像并上传至 OSS。"""
        async def fake_upload(*args, **kwargs):
            return "https://fake-oss.example.com/avatars/updated.jpg"

        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints.users.oss_client.upload_image_to_oss",
            fake_upload,
        )

        user = await _create_user(db_session, "avatar_update_user")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            data={"nickname": "NewName"},
            files={"avatar": ("avatar.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg")},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["nickname"] == "NewName"
        assert data["avatar_url"] == "https://fake-oss.example.com/avatars/updated.jpg"

    async def test_update_invalid_avatar_type(self, client: TestClient, db_session: AsyncSession):
        """测试上传非法格式头像时返回 422。"""
        user = await _create_user(db_session, "bad_avatar_update")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            data={"nickname": "NewName"},
            files={"avatar": ("readme.txt", b"not an image", "text/plain")},
        )
        assert resp.status_code == 422


class TestGetUser:
    """测试获取用户公开资料。"""

    async def test_get_public_profile(self, client: TestClient, db_session: AsyncSession):
        """测试获取正常用户的公开资料，敏感字段不应返回。"""
        user = await _create_user(db_session, "public_user")
        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["username"] == "public_user"
        # sensitive fields should not be present
        assert "email" not in data
        assert "phone" not in data

    async def test_get_deleted_user(self, client: TestClient, db_session: AsyncSession):
        """测试获取已删除用户时返回 404。"""
        user = await _create_user(db_session, "deleted_pub")
        user.is_deleted = True
        await db_session.commit()
        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 404

    async def test_get_public_profile_cache_hit(
        self, client: TestClient, db_session: AsyncSession
    ):
        """用户公开资料二次请求应命中缓存。"""
        user = await _create_user(db_session, "public_cache_hit")
        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 200
        assert api_data(resp)["username"] == "public_cache_hit"
        cached_nickname = api_data(resp)["nickname"]

        user.nickname = "ModifiedNickname"
        await db_session.commit()

        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 200
        assert api_data(resp)["nickname"] == cached_nickname

    async def test_get_public_profile_cache_invalidated_on_update(
        self, client: TestClient, db_session: AsyncSession, fake_redis
    ):
        """用户更新资料后公开资料缓存应被失效。"""
        from echomemory_backend.core.cache.general import USER_PUBLIC_PREFIX, build_cache_key

        user = await _create_user(db_session, "public_cache_inv")

        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 200

        cache_key = build_cache_key(USER_PUBLIC_PREFIX, user.id)
        assert await fake_redis.exists(cache_key) == 1

        resp = client.patch(
            f"{BASE}/me",
            headers=_auth_header(user),
            json={"nickname": "NewNickname"},
        )
        assert resp.status_code == 200

        assert await fake_redis.exists(cache_key) == 0


class TestSearchUsers:
    """测试用户搜索功能。"""

    async def test_search_by_username(self, client: TestClient, db_session: AsyncSession):
        """测试按用户名关键字搜索并命中结果。"""
        await _create_user(db_session, "searchable")
        resp = client.get(SEARCH_URL, params={"q": "search"})
        assert resp.status_code == 200
        data = api_data(resp)
        assert len(data["items"]) >= 1
        assert data["items"][0]["username"] == "searchable"

    async def test_search_no_match(self, client: TestClient):
        """测试搜索无匹配结果时返回空列表。"""
        resp = client.get(SEARCH_URL, params={"q": "zzzzzzzzz"})
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_search_includes_follow_status(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试登录用户搜索时返回 is_followed_by_me 状态。"""
        me = await _create_user(db_session, "search_follower")
        followed = await _create_user(db_session, "search_followed")
        await _create_user(db_session, "search_stranger")
        db_session.add(UserFollow(follower_id=me.id, followee_id=followed.id))
        await db_session.commit()

        resp = client.get(
            SEARCH_URL,
            params={"q": "search_"},
            headers=_auth_header(me),
        )
        assert resp.status_code == 200
        by_username = {item["username"]: item for item in api_data(resp)["items"]}
        assert by_username["search_followed"]["is_followed_by_me"] is True
        assert by_username["search_stranger"]["is_followed_by_me"] is False


class TestGetUserFollowStatus:
    """测试公开资料中的关注状态字段。"""

    async def test_profile_shows_followed_status(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试已关注用户资料中 is_followed_by_me 为 true。"""
        me = await _create_user(db_session, "profile_follower")
        target = await _create_user(db_session, "profile_target")
        db_session.add(UserFollow(follower_id=me.id, followee_id=target.id))
        await db_session.commit()

        resp = client.get(f"{BASE}/{target.id}", headers=_auth_header(me))
        assert resp.status_code == 200
        assert api_data(resp)["is_followed_by_me"] is True

    async def test_profile_not_followed_status(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试未关注用户资料中 is_followed_by_me 为 false。"""
        me = await _create_user(db_session, "profile_not_follower")
        target = await _create_user(db_session, "profile_not_target")

        resp = client.get(f"{BASE}/{target.id}", headers=_auth_header(me))
        assert resp.status_code == 200
        assert api_data(resp)["is_followed_by_me"] is False

    async def test_own_profile_follow_status_false(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试查看自己资料时 is_followed_by_me 为 false。"""
        me = await _create_user(db_session, "profile_self")
        resp = client.get(f"{BASE}/{me.id}", headers=_auth_header(me))
        assert resp.status_code == 200
        assert api_data(resp)["is_followed_by_me"] is False


class TestFollow:
    """测试用户关注与取消关注功能。"""

    async def test_follow_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常关注其他用户。"""
        me = await _create_user(db_session, "follower")
        target = await _create_user(db_session, "followee")
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        result = await db_session.execute(
            select(Notification).where(
                Notification.recipient_id == target.id,
                Notification.actor_id == me.id,
            )
        )
        notification = result.scalar_one()
        assert notification.target_type == "user"
        assert notification.target_id == me.id

    async def test_follow_self_fails(self, client: TestClient, db_session: AsyncSession):
        """测试关注自己时返回 400。"""
        me = await _create_user(db_session, "self_follow")
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": me.id}
        )
        assert resp.status_code == 400

    async def test_follow_duplicate_fails(self, client: TestClient, db_session: AsyncSession):
        """测试重复关注同一用户时返回 409。"""
        me = await _create_user(db_session, "dup_follower")
        target = await _create_user(db_session, "dup_followee")
        client.post(FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id})
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 409

    async def test_unfollow_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消关注。"""
        me = await _create_user(db_session, "un_follower")
        target = await _create_user(db_session, "un_followee")
        db_session.add(UserFollow(follower_id=me.id, followee_id=target.id))
        await db_session.commit()
        resp = client.post(
            UNFOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

    async def test_unfollow_not_following_fails(self, client: TestClient, db_session: AsyncSession):
        """测试取消未关注的用户时返回 400。"""
        me = await _create_user(db_session, "not_following")
        target = await _create_user(db_session, "not_followee")
        resp = client.post(
            UNFOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 400

    async def test_get_followees(self, client: TestClient, db_session: AsyncSession):
        """测试获取当前用户的关注列表。"""
        me = await _create_user(db_session, "list_follower")
        target = await _create_user(db_session, "list_followee")
        db_session.add(UserFollow(follower_id=me.id, followee_id=target.id))
        await db_session.commit()
        resp = client.get(f"{BASE}/{me.id}/followees")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["username"] == "list_followee"

    async def test_get_followers(self, client: TestClient, db_session: AsyncSession):
        """测试获取当前用户的粉丝列表。"""
        follower = await _create_user(db_session, "fan")
        me = await _create_user(db_session, "celebrity")
        db_session.add(UserFollow(follower_id=follower.id, followee_id=me.id))
        await db_session.commit()
        resp = client.get(f"{BASE}/{me.id}/followers")
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["username"] == "fan"


class TestAdmin:
    """测试管理员对用户的管理操作。"""

    async def test_admin_list_users(self, client: TestClient, db_session: AsyncSession):
        """测试管理员获取用户列表（分页响应格式）。"""
        admin = await _create_user(db_session, "admin_user", role=UserRole.ADMIN.value)
        await _create_user(db_session, "regular")
        resp = client.get(ADMIN_LIST_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        data = api_data(resp)
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) >= 1
        assert data["total"] >= 1

    async def test_admin_list_forbidden_for_normal_user(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户访问管理员列表接口返回 403。"""
        user = await _create_user(db_session, "normal_user")
        resp = client.get(ADMIN_LIST_URL, headers=_auth_header(user))
        assert resp.status_code == 403

    async def test_admin_ban_user(self, client: TestClient, db_session: AsyncSession):
        """测试管理员封禁用户。"""
        admin = await _create_user(db_session, "admin_ban", role=UserRole.ADMIN.value)
        target = await _create_user(db_session, "to_ban")
        resp = client.post(
            f"{BASE}/{target.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 200
        assert api_data(resp)["status"] == UserStatus.BANNED.value

    async def test_admin_ban_invalid_ban_duration_returns_422(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试非法 ban_duration 返回 422 且包含字段级错误详情。"""
        admin = await _create_user(db_session, "admin_bad_ban", role=UserRole.ADMIN.value)
        target = await _create_user(db_session, "bad_ban_target")
        resp = client.post(
            f"{BASE}/{target.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.MUTED.value, "ban_duration": "bad"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] != 0
        assert body["data"] is not None
        assert "errors" in body["data"]
        assert isinstance(body["data"]["errors"], list)

    async def test_admin_unban_user(self, client: TestClient, db_session: AsyncSession):
        """测试管理员解封用户。"""
        admin = await _create_user(db_session, "admin_unban", role=UserRole.ADMIN.value)
        target = await _create_user(db_session, "to_unban")
        target.status = UserStatus.BANNED.value
        target.banned_at = func.now()
        await db_session.commit()
        resp = client.post(
            f"{BASE}/{target.id}/unban",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert api_data(resp)["status"] == UserStatus.ACTIVE.value

    async def test_admin_cannot_ban_super_admin(self, client: TestClient, db_session: AsyncSession):
        """测试管理员无法封禁超级管理员。"""
        admin = await _create_user(db_session, "admin_limited", role=UserRole.ADMIN.value)
        super_admin = await _create_user(db_session, "super", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            f"{BASE}/{super_admin.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    async def test_admin_update_user(self, client: TestClient, db_session: AsyncSession):
        """测试管理员更新普通用户的角色与安全评分。"""
        admin = await _create_user(db_session, "admin_patch", role=UserRole.ADMIN.value)
        target = await _create_user(db_session, "to_patch")
        resp = client.patch(
            f"{BASE}/{target.id}/admin",
            headers=_auth_header(admin),
            json={"role": UserRole.VIP.value, "safety_score": 5},
        )
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["role"] == UserRole.VIP.value
        assert data["safety_score"] == 5

    async def test_admin_cannot_ban_other_admin(self, client: TestClient, db_session: AsyncSession):
        """测试管理员无法封禁其他管理员（同级权限）。"""
        admin = await _create_user(db_session, "admin_a", role=UserRole.ADMIN.value)
        other_admin = await _create_user(db_session, "admin_b", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE}/{other_admin.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    async def test_admin_cannot_ban_self(self, client: TestClient, db_session: AsyncSession):
        """测试管理员不能封禁自己。"""
        admin = await _create_user(db_session, "admin_self_ban", role=UserRole.ADMIN.value)
        resp = client.post(
            f"{BASE}/{admin.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    async def test_super_admin_cannot_ban_self(self, client: TestClient, db_session: AsyncSession):
        """测试超级管理员不能封禁自己。"""
        super_admin = await _create_user(db_session, "sa_self_ban", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            f"{BASE}/{super_admin.id}/ban",
            headers=_auth_header(super_admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    async def test_super_admin_cannot_ban_other_super_admin(self, client: TestClient, db_session: AsyncSession):
        """测试超级管理员无法封禁其他超级管理员。"""
        sa1 = await _create_user(db_session, "sa_one", role=UserRole.SUPER_ADMIN.value)
        sa2 = await _create_user(db_session, "sa_two", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            f"{BASE}/{sa2.id}/ban",
            headers=_auth_header(sa1),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    async def test_admin_create_user_success(self, client: TestClient, db_session: AsyncSession):
        """测试管理员创建普通用户成功。"""
        admin = await _create_user(db_session, "admin_creator", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(admin),
            json={
                "username": "newuser1",
                "nickname": "New User",
                "password": "password123",
                "email": "new@example.com",
                "role": UserRole.USER.value,
            },
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["username"] == "newuser1"
        assert data["nickname"] == "New User"
        assert data["role"] == UserRole.USER.value
        assert data["email"] == "new@example.com"

        stmt = select(Playlist).where(
            Playlist.user_id == data["id"],
            Playlist.is_like.is_(True),
        )
        playlist = (await db_session.execute(stmt)).scalar_one()
        assert playlist.title == "我喜欢的音乐"
        assert playlist.is_private is True

    async def test_admin_create_user_with_full_fields(self, client: TestClient, db_session: AsyncSession):
        """测试超级管理员创建用户并指定所有可选字段。"""
        super_admin = await _create_user(db_session, "sa_creator", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(super_admin),
            json={
                "username": "fulluser",
                "nickname": "Full User",
                "password": "password123",
                "email": "full@example.com",
                "phone": "13800138000",
                "gender": 1,
                "birth": "2000-01-01",
                "bio": "Test bio",
                "city": "Beijing",
                "role": UserRole.ADMIN.value,
                "status": UserStatus.ACTIVE.value,
                "safety_score": 8,
                "is_verified": True,
                "exp": 100,
            },
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["username"] == "fulluser"
        assert data["role"] == UserRole.ADMIN.value
        assert data["safety_score"] == 8
        assert data["is_verified"] is True
        assert data["exp"] == 100

    async def test_admin_cannot_create_admin_user(self, client: TestClient, db_session: AsyncSession):
        """测试普通管理员不能创建管理员角色的用户。"""
        admin = await _create_user(db_session, "admin_limited2", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(admin),
            json={
                "username": "shouldfail",
                "nickname": "Should Fail",
                "password": "password123",
                "role": UserRole.ADMIN.value,
            },
        )
        assert resp.status_code == 403

    async def test_admin_cannot_create_super_admin_user(self, client: TestClient, db_session: AsyncSession):
        """测试普通管理员不能创建超级管理员角色的用户。"""
        admin = await _create_user(db_session, "admin_limited3", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(admin),
            json={
                "username": "shouldfail2",
                "nickname": "Should Fail 2",
                "password": "password123",
                "role": UserRole.SUPER_ADMIN.value,
            },
        )
        assert resp.status_code == 403

    async def test_super_admin_can_create_admin_user(self, client: TestClient, db_session: AsyncSession):
        """测试超级管理员可以创建管理员角色的用户。"""
        super_admin = await _create_user(db_session, "sa_grant", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(super_admin),
            json={
                "username": "newadmin",
                "nickname": "New Admin",
                "password": "password123",
                "role": UserRole.ADMIN.value,
            },
        )
        assert resp.status_code == 201
        assert api_data(resp)["role"] == UserRole.ADMIN.value

    async def test_admin_create_duplicate_username(self, client: TestClient, db_session: AsyncSession):
        """测试管理员创建用户名已存在的用户返回 409。"""
        admin = await _create_user(db_session, "admin_dup", role=UserRole.ADMIN.value)
        await _create_user(db_session, "existing_user")
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(admin),
            json={
                "username": "existing_user",
                "nickname": "Duplicate",
                "password": "password123",
            },
        )
        assert resp.status_code == 409

    async def test_admin_create_duplicate_email(self, client: TestClient, db_session: AsyncSession):
        """测试管理员创建邮箱已存在的用户返回 409。"""
        admin = await _create_user(db_session, "admin_dup_email", role=UserRole.ADMIN.value)
        await _create_user(db_session, "email_owner2", email="dup@example.com")
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(admin),
            json={
                "username": "newuser_email",
                "nickname": "New User",
                "password": "password123",
                "email": "dup@example.com",
            },
        )
        assert resp.status_code == 409

    async def test_normal_user_cannot_create_user_via_admin(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户不能通过管理员接口创建用户。"""
        user = await _create_user(db_session, "normal_user2")
        resp = client.post(
            ADMIN_CREATE_URL,
            headers=_auth_header(user),
            json={
                "username": "shouldfail3",
                "nickname": "Should Fail 3",
                "password": "password123",
            },
        )
        assert resp.status_code == 403



# ============================================================================
# 管理仪表盘统计
# ============================================================================


class TestAdminDashboardStats:
    """测试管理仪表盘统计接口。"""

    ADMIN_STATS_URL = f"{BASE}/admin/stats"

    async def test_stats_as_admin(self, client: TestClient, db_session: AsyncSession):
        """测试管理员获取统计数据。"""
        admin = await _create_user(db_session, "stats_admin", role=UserRole.ADMIN.value)

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        data = api_data(resp)
        for key in (
            "users",
            "music",
            "albums",
            "playlists",
            "comments",
            "space_posts",
            "user_status_distribution",
            "user_role_distribution",
            "content_trend",
            "music_style_distribution",
            "moderation_queue",
            "engagement_totals",
            "top_hot_music",
            "agent_run_summary",
        ):
            assert key in data
        assert isinstance(data["users"], int)
        assert isinstance(data["content_trend"], list)
        assert isinstance(data["moderation_queue"], dict)
        assert isinstance(data["agent_run_summary"], dict)

    async def test_stats_as_normal_user_forbidden(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户访问统计接口返回 403。"""
        user = await _create_user(db_session, "stats_normal")

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(user))
        assert resp.status_code == 403

    async def test_stats_unauthorized(self, client: TestClient):
        """测试未登录访问统计接口返回 401。"""
        resp = client.get(self.ADMIN_STATS_URL)
        assert resp.status_code == 401

    async def test_stats_cache_hit(
        self, client: TestClient, db_session: AsyncSession
    ):
        """仪表盘统计二次请求应命中缓存。"""
        admin = await _create_user(
            db_session, "stats_cache_hit_admin", role=UserRole.ADMIN.value
        )

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        first_count = api_data(resp)["users"]

        # 绕过业务层直接写入用户，避免触发缓存失效
        from echomemory_backend.core.security.security import get_password_hash

        db_session.add(
            User(
                username="stats_cache_hit_user",
                password_hash=get_password_hash("secret"),
                nickname="stats_cache_hit_user",
            )
        )
        await db_session.commit()

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        assert api_data(resp)["users"] == first_count

    async def test_stats_cache_invalidated_on_user_register(
        self, client: TestClient, db_session: AsyncSession, fake_redis
    ):
        """新用户注册后仪表盘统计缓存应被失效。"""
        from echomemory_backend.core.cache.general import ADMIN_DASHBOARD_STATS_PREFIX, build_cache_key

        admin = await _create_user(
            db_session, "stats_cache_inv_admin", role=UserRole.ADMIN.value
        )

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        first_count = api_data(resp)["users"]

        cache_key = build_cache_key(ADMIN_DASHBOARD_STATS_PREFIX)
        assert await fake_redis.exists(cache_key) == 1

        resp = client.post(
            "/api/v1/auth/register",
            data={
                "username": "stats_cache_inv_user",
                "nickname": "stats_cache_inv_user",
                "password": "secret123",
            },
        )
        assert resp.status_code == 201

        assert await fake_redis.exists(cache_key) == 0

        resp = client.get(self.ADMIN_STATS_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        assert api_data(resp)["users"] == first_count + 1
