import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy.orm import Session

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User, UserFollow

BASE = "/api/v1/users"
ME_URL = f"{BASE}/me"
SEARCH_URL = f"{BASE}/"
FOLLOW_URL = f"{BASE}/follow"
UNFOLLOW_URL = f"{BASE}/unfollow"
ADMIN_LIST_URL = f"{BASE}/admin/list"


def _create_user(db: Session, username: str, password: str = "secret", role: int = UserRole.USER.value, status: int = UserStatus.ACTIVE.value, **kwargs) -> User:
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
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


class TestUpdateMe:
    def test_update_nickname(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "updater")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            json={"nickname": "NewName"},
        )
        assert resp.status_code == 200
        assert resp.json()["nickname"] == "NewName"

    def test_update_email_conflict(self, client: TestClient, db_session: Session):
        _create_user(db_session, "email_owner", email="taken@example.com")
        user = _create_user(db_session, "updater2")
        resp = client.patch(
            ME_URL,
            headers=_auth_header(user),
            json={"email": "taken@example.com"},
        )
        assert resp.status_code == 409

    def test_update_unauthorized(self, client: TestClient):
        resp = client.patch(ME_URL, json={"nickname": "x"})
        assert resp.status_code == 401


class TestGetUser:
    def test_get_public_profile(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "public_user")
        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "public_user"
        # sensitive fields should not be present
        assert "email" not in data
        assert "phone" not in data

    def test_get_deleted_user(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "deleted_pub")
        user.is_deleted = True
        db_session.commit()
        resp = client.get(f"{BASE}/{user.id}")
        assert resp.status_code == 404


class TestSearchUsers:
    def test_search_by_username(self, client: TestClient, db_session: Session):
        _create_user(db_session, "searchable")
        resp = client.get(SEARCH_URL, params={"q": "search"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["username"] == "searchable"

    def test_search_no_match(self, client: TestClient):
        resp = client.get(SEARCH_URL, params={"q": "zzzzzzzzz"})
        assert resp.status_code == 200
        assert resp.json() == []


class TestFollow:
    def test_follow_success(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "follower")
        target = _create_user(db_session, "followee")
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 204

    def test_follow_self_fails(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "self_follow")
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": me.id}
        )
        assert resp.status_code == 400

    def test_follow_duplicate_fails(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "dup_follower")
        target = _create_user(db_session, "dup_followee")
        client.post(FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id})
        resp = client.post(
            FOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 409

    def test_unfollow_success(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "un_follower")
        target = _create_user(db_session, "un_followee")
        db_session.add(UserFollow(follower_id=me.id, followee_id=target.id))
        db_session.commit()
        resp = client.post(
            UNFOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 204

    def test_unfollow_not_following_fails(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "not_following")
        target = _create_user(db_session, "not_followee")
        resp = client.post(
            UNFOLLOW_URL, headers=_auth_header(me), json={"followee_id": target.id}
        )
        assert resp.status_code == 404

    def test_get_followees(self, client: TestClient, db_session: Session):
        me = _create_user(db_session, "list_follower")
        target = _create_user(db_session, "list_followee")
        db_session.add(UserFollow(follower_id=me.id, followee_id=target.id))
        db_session.commit()
        resp = client.get(f"{BASE}/{me.id}/followees")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "list_followee"

    def test_get_followers(self, client: TestClient, db_session: Session):
        follower = _create_user(db_session, "fan")
        me = _create_user(db_session, "celebrity")
        db_session.add(UserFollow(follower_id=follower.id, followee_id=me.id))
        db_session.commit()
        resp = client.get(f"{BASE}/{me.id}/followers")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "fan"


class TestAdmin:
    def test_admin_list_users(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_user", role=UserRole.ADMIN.value)
        _create_user(db_session, "regular")
        resp = client.get(ADMIN_LIST_URL, headers=_auth_header(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_admin_list_forbidden_for_normal_user(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_user")
        resp = client.get(ADMIN_LIST_URL, headers=_auth_header(user))
        assert resp.status_code == 403

    def test_admin_ban_user(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_ban", role=UserRole.ADMIN.value)
        target = _create_user(db_session, "to_ban")
        resp = client.post(
            f"{BASE}/{target.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == UserStatus.BANNED.value

    def test_admin_unban_user(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_unban", role=UserRole.ADMIN.value)
        target = _create_user(db_session, "to_unban")
        target.status = UserStatus.BANNED.value
        target.banned_at = func.now()
        db_session.commit()
        resp = client.post(
            f"{BASE}/{target.id}/unban",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == UserStatus.ACTIVE.value

    def test_admin_cannot_ban_super_admin(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_limited", role=UserRole.ADMIN.value)
        super_admin = _create_user(db_session, "super", role=UserRole.SUPER_ADMIN.value)
        resp = client.post(
            f"{BASE}/{super_admin.id}/ban",
            headers=_auth_header(admin),
            json={"status": UserStatus.BANNED.value},
        )
        assert resp.status_code == 403

    def test_admin_update_user(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_patch", role=UserRole.ADMIN.value)
        target = _create_user(db_session, "to_patch")
        resp = client.patch(
            f"{BASE}/{target.id}/admin",
            headers=_auth_header(admin),
            json={"role": UserRole.VIP.value, "safety_score": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == UserRole.VIP.value
        assert data["safety_score"] == 5
