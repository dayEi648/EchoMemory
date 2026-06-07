import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.space_post import SpacePost, SpacePostImage, SpacePostLike
from echomemory_backend.models.user import User

BASE = "/api/v1/space-posts"


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _create_user(db: AsyncSession, username: str, password: str = "secret", role: int = UserRole.USER.value) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=username.capitalize(),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_post(db: AsyncSession, user_id: int, content: str | None = "Hello", is_private: bool = False, is_deleted: bool = False) -> SpacePost:
    post = SpacePost(
        user_id=user_id,
        content=content,
        is_private=is_private,
        is_deleted=is_deleted,
        post_type="original",
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


class TestCreateSpacePost:
    async def test_create_text_only(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "poster")
        resp = client.post(
            BASE,
            headers=_auth_header(user),
            data={"content": "My first post", "is_private": "false"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "My first post"
        assert data["user_id"] == user.id
        assert data["is_private"] is False
        assert data["images"] == []

    async def test_create_with_images(self, client: TestClient, db_session: AsyncSession, monkeypatch):
        uploaded: list[str] = []

        async def fake_upload(*args, **kwargs):
            url = f"https://fake-oss.example.com/space/{len(uploaded)}.jpg"
            uploaded.append(url)
            return url

        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints.space_post.upload_image_to_oss", fake_upload
        )

        user = await _create_user(db_session, "img_poster")
        resp = client.post(
            BASE,
            headers=_auth_header(user),
            data={"content": "With images"},
            files=[
                ("files", ("a.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg")),
                ("files", ("b.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg")),
            ],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["images"]) == 2
        assert data["images"][0]["ordinal"] == 0
        assert data["images"][1]["ordinal"] == 1

    async def test_create_unauthorized(self, client: TestClient):
        resp = client.post(BASE, data={"content": "x"})
        assert resp.status_code == 401


class TestGetSpacePost:
    async def test_get_public_post(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "public_poster")
        post = await _create_post(db_session, user.id, "Public content")
        db_session.add(SpacePostImage(post_id=post.id, image_url="https://example.com/1.jpg", ordinal=0))
        await db_session.commit()

        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Public content"
        assert len(data["images"]) == 1

    async def test_get_private_post_by_owner(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "private_owner")
        post = await _create_post(db_session, user.id, "Private", is_private=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["content"] == "Private"

    async def test_get_private_post_by_other(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "private_owner2")
        other = await _create_user(db_session, "private_viewer")
        post = await _create_post(db_session, owner.id, "Private", is_private=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(other))
        assert resp.status_code == 403

    async def test_get_deleted_post(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "deleted_poster")
        post = await _create_post(db_session, user.id, "Deleted", is_deleted=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 404


class TestListSpacePosts:
    async def test_list_own_posts_include_private(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_owner")
        await _create_post(db_session, user.id, "Public")
        await _create_post(db_session, user.id, "Private", is_private=True)

        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_list_others_exclude_private(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "list_owner2")
        viewer = await _create_user(db_session, "list_viewer")
        await _create_post(db_session, owner.id, "Public")
        await _create_post(db_session, owner.id, "Private", is_private=True)

        resp = client.get(BASE, params={"user_id": owner.id}, headers=_auth_header(viewer))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "Public"

    async def test_list_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_deleted")
        await _create_post(db_session, user.id, "Active")
        await _create_post(db_session, user.id, "Deleted", is_deleted=True)

        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "Active"


class TestSoftDelete:
    async def test_delete_own_post(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "soft_deleter")
        post = await _create_post(db_session, user.id, "To delete")
        resp = client.delete(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 204

        resp2 = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp2.status_code == 404

    async def test_delete_others_post(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "soft_owner")
        other = await _create_user(db_session, "soft_other")
        post = await _create_post(db_session, owner.id, "Not mine")
        resp = client.delete(f"{BASE}/{post.id}", headers=_auth_header(other))
        assert resp.status_code == 403


class TestLike:
    async def test_like_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "liker")
        post = await _create_post(db_session, user.id, "Like me")
        resp = client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 201

    async def test_like_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "liker2")
        post = await _create_post(db_session, user.id, "Like me2")
        client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        resp = client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 201

    async def test_unlike_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "unliker")
        post = await _create_post(db_session, user.id, "Unlike me")
        db_session.add(SpacePostLike(post_id=post.id, user_id=user.id))
        await db_session.commit()

        resp = client.delete(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 204

    async def test_unlike_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "unliker2")
        post = await _create_post(db_session, user.id, "Unlike me2")
        resp = client.delete(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 204


class TestAdminHardDelete:
    async def test_admin_hard_delete(self, client: TestClient, db_session: AsyncSession, monkeypatch):
        deleted_urls: list[str] = []

        async def fake_delete(url: str):
            deleted_urls.append(url)

        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints.space_post.delete_object_by_url", fake_delete
        )

        admin = await _create_user(db_session, "admin_hd", role=UserRole.ADMIN.value)
        user = await _create_user(db_session, "target_hd")
        post = await _create_post(db_session, user.id, "Hard delete me")
        db_session.add(SpacePostImage(post_id=post.id, image_url="https://oss.example.com/1.jpg", ordinal=0))
        await db_session.commit()

        resp = client.delete(f"{BASE}/admin/{post.id}", headers=_auth_header(admin))
        assert resp.status_code == 204
        assert "https://oss.example.com/1.jpg" in deleted_urls

        resp2 = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp2.status_code == 404

    async def test_normal_user_cannot_hard_delete(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "normal_hd")
        post = await _create_post(db_session, user.id, "No hard delete")
        resp = client.delete(f"{BASE}/admin/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 403
