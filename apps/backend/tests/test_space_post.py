import io

from fastapi import HTTPException
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
    """测试创建空间动态（SpacePost）的相关场景。"""

    async def test_create_text_only(self, client: TestClient, db_session: AsyncSession):
        """测试仅包含文本内容创建动态成功。"""
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
        """测试创建动态时上传图片成功并返回正确顺序。"""
        uploaded: list[str] = []

        async def fake_upload(*args, **kwargs):
            url = f"https://fake-oss.example.com/space/{len(uploaded)}.jpg"
            uploaded.append(url)
            return url

        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints._upload_helpers.upload_optional_image",
            fake_upload,
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
        """测试未登录用户创建动态返回 401。"""
        resp = client.post(BASE, data={"content": "x"})
        assert resp.status_code == 401

    async def test_create_cleans_uploaded_images_when_later_upload_fails(
        self,
        client: TestClient,
        db_session: AsyncSession,
        monkeypatch,
    ):
        """测试多图上传中后续图片失败时清理此前已上传图片。"""
        uploaded_urls = ["https://fake-oss.example.com/space/0.jpg"]
        deleted_urls: list[str] = []
        call_count = 0

        async def fake_upload(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return uploaded_urls[0]
            raise HTTPException(status_code=422, detail="image failed")

        async def fake_delete(url: str):
            deleted_urls.append(url)

        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints.space_post.upload_optional_image",
            fake_upload,
        )
        monkeypatch.setattr(
            "echomemory_backend.core.oss_client.delete_object_by_url",
            fake_delete,
        )

        user = await _create_user(db_session, "img_cleanup")
        resp = client.post(
            BASE,
            headers=_auth_header(user),
            data={"content": "With images"},
            files=[
                ("files", ("a.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg")),
                ("files", ("b.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg")),
            ],
        )

        assert resp.status_code == 422
        assert deleted_urls == uploaded_urls


class TestGetSpacePost:
    """测试获取单条空间动态（SpacePost）的相关场景。"""

    async def test_get_public_post(self, client: TestClient, db_session: AsyncSession):
        """测试获取公开动态成功并返回图片列表。"""
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
        """测试动态所有者获取自己的私有动态成功。"""
        user = await _create_user(db_session, "private_owner")
        post = await _create_post(db_session, user.id, "Private", is_private=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["content"] == "Private"

    async def test_get_private_post_by_other(self, client: TestClient, db_session: AsyncSession):
        """测试其他用户获取私有动态返回 403。"""
        owner = await _create_user(db_session, "private_owner2")
        other = await _create_user(db_session, "private_viewer")
        post = await _create_post(db_session, owner.id, "Private", is_private=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(other))
        assert resp.status_code == 403

    async def test_get_deleted_post(self, client: TestClient, db_session: AsyncSession):
        """测试获取已删除的动态返回 404。"""
        user = await _create_user(db_session, "deleted_poster")
        post = await _create_post(db_session, user.id, "Deleted", is_deleted=True)
        resp = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 404


class TestListSpacePosts:
    """测试列表查询空间动态（SpacePost）的相关场景。"""

    async def test_list_own_posts_include_private(self, client: TestClient, db_session: AsyncSession):
        """测试查询自己的动态时同时返回公开和私有动态。"""
        user = await _create_user(db_session, "list_owner")
        await _create_post(db_session, user.id, "Public")
        await _create_post(db_session, user.id, "Private", is_private=True)

        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["like_count"] == 0
            assert item["liked_by_me"] is False

    async def test_list_posts_includes_like_status(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试动态列表返回点赞数与当前用户点赞状态。"""
        user = await _create_user(db_session, "post_like_user")
        post = await _create_post(db_session, user.id, "Liked post")
        db_session.add(SpacePostLike(post_id=post.id, user_id=user.id))
        await db_session.commit()

        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 200
        item = next(i for i in resp.json()["items"] if i["id"] == post.id)
        assert item["like_count"] == 1
        assert item["liked_by_me"] is True

    async def test_list_others_exclude_private(self, client: TestClient, db_session: AsyncSession):
        """测试查询他人动态时不包含私有动态。"""
        owner = await _create_user(db_session, "list_owner2")
        viewer = await _create_user(db_session, "list_viewer")
        await _create_post(db_session, owner.id, "Public")
        await _create_post(db_session, owner.id, "Private", is_private=True)

        resp = client.get(BASE, params={"user_id": owner.id}, headers=_auth_header(viewer))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Public"

    async def test_list_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        """测试列表查询自动排除已删除的动态。"""
        user = await _create_user(db_session, "list_deleted")
        await _create_post(db_session, user.id, "Active")
        await _create_post(db_session, user.id, "Deleted", is_deleted=True)

        resp = client.get(BASE, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["content"] == "Active"


class TestSoftDelete:
    """测试软删除空间动态（SpacePost）的相关场景。"""

    async def test_delete_own_post(self, client: TestClient, db_session: AsyncSession):
        """测试删除自己的动态成功后无法再访问。"""
        user = await _create_user(db_session, "soft_deleter")
        post = await _create_post(db_session, user.id, "To delete")
        resp = client.delete(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 204

        resp2 = client.get(f"{BASE}/{post.id}", headers=_auth_header(user))
        assert resp2.status_code == 404

    async def test_delete_others_post(self, client: TestClient, db_session: AsyncSession):
        """测试删除他人动态返回 403。"""
        owner = await _create_user(db_session, "soft_owner")
        other = await _create_user(db_session, "soft_other")
        post = await _create_post(db_session, owner.id, "Not mine")
        resp = client.delete(f"{BASE}/{post.id}", headers=_auth_header(other))
        assert resp.status_code == 403


class TestLike:
    """测试空间动态点赞（Like）与取消点赞的相关场景。"""

    async def test_like_success(self, client: TestClient, db_session: AsyncSession):
        """测试对动态点赞成功。"""
        user = await _create_user(db_session, "liker")
        post = await _create_post(db_session, user.id, "Like me")
        resp = client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 201

    async def test_like_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试重复点赞保持幂等性（不会报错）。"""
        user = await _create_user(db_session, "liker2")
        post = await _create_post(db_session, user.id, "Like me2")
        client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        resp = client.post(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 201

    async def test_unlike_success(self, client: TestClient, db_session: AsyncSession):
        """测试取消点赞成功。"""
        user = await _create_user(db_session, "unliker")
        post = await _create_post(db_session, user.id, "Unlike me")
        db_session.add(SpacePostLike(post_id=post.id, user_id=user.id))
        await db_session.commit()

        resp = client.delete(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 204

    async def test_unlike_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试重复取消点赞保持幂等性（不会报错）。"""
        user = await _create_user(db_session, "unliker2")
        post = await _create_post(db_session, user.id, "Unlike me2")
        resp = client.delete(f"{BASE}/{post.id}/like", headers=_auth_header(user))
        assert resp.status_code == 204


class TestAdminHardDelete:
    """测试管理员硬删除空间动态（SpacePost）的相关场景。"""

    async def test_admin_hard_delete(self, client: TestClient, db_session: AsyncSession, monkeypatch):
        """测试管理员硬删除动态及其关联图片成功。"""
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
        """测试普通用户调用管理员硬删除接口返回 403。"""
        user = await _create_user(db_session, "normal_hd")
        post = await _create_post(db_session, user.id, "No hard delete")
        resp = client.delete(f"{BASE}/admin/{post.id}", headers=_auth_header(user))
        assert resp.status_code == 403


# ============================================================================
# user.like_count 维护（空间动态）
# ============================================================================


class TestUserLikeCountFromSpacePost:
    """测试空间动态点赞/取消时自动维护 post.user.like_count。"""

    async def test_like_post_increases_author_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试点赞动态后作者的 like_count 增加。"""
        author = await _create_user(db_session, "sp_author_like")
        liker = await _create_user(db_session, "sp_liker")
        post = await _create_post(db_session, author.id, "Like my post")

        assert author.like_count == 0
        client.post(f"{BASE}/{post.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 1

    async def test_unlike_post_decreases_author_like_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试取消点赞后作者的 like_count 减少。"""
        author = await _create_user(db_session, "sp_author_unlike")
        liker = await _create_user(db_session, "sp_unliker")
        post = await _create_post(db_session, author.id, "Unlike my post")

        client.post(f"{BASE}/{post.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 1

        client.delete(f"{BASE}/{post.id}/like", headers=_auth_header(liker))
        await db_session.refresh(author)
        assert author.like_count == 0


# ============================================================================
# 转发
# ============================================================================


class TestForwardToSpace:
    """测试转发内容到空间动态。"""

    async def test_forward_space_post(self, client: TestClient, db_session: AsyncSession):
        """测试转发别人的动态到自己的空间。"""
        author = await _create_user(db_session, "fw_author")
        forwarder = await _create_user(db_session, "fw_forwarder")
        post = await _create_post(db_session, author.id, "Original post")

        resp = client.post(
            f"{BASE}/forward",
            headers=_auth_header(forwarder),
            data={"source_type": "space_post", "source_id": post.id, "content": "Check this!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == forwarder.id
        assert data["content"] == "Check this!"

        # 源动态 forward_count 递增
        await db_session.refresh(post)
        assert post.forward_count == 1

    async def test_forward_private_post_blocked(self, client: TestClient, db_session: AsyncSession):
        """测试转发私密动态返回 404。"""
        author = await _create_user(db_session, "fw_private_author")
        forwarder = await _create_user(db_session, "fw_private_user")
        post = await _create_post(db_session, author.id, "Secret", is_private=True)

        resp = client.post(
            f"{BASE}/forward",
            headers=_auth_header(forwarder),
            data={"source_type": "space_post", "source_id": post.id},
        )
        assert resp.status_code == 404

    async def test_forward_invalid_source_type(self, client: TestClient, db_session: AsyncSession):
        """测试转发无效 source_type 返回 400。"""
        user = await _create_user(db_session, "fw_invalid")
        resp = client.post(
            f"{BASE}/forward",
            headers=_auth_header(user),
            data={"source_type": "invalid", "source_id": 1},
        )
        assert resp.status_code == 400
