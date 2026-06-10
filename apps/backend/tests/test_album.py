"""专辑模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.dictionary import EmotionTag, InterestTag
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/albums"
ADMIN_BASE_URL = f"{BASE_URL}/admin"


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


async def _create_user(
    db: AsyncSession,
    username: str,
    role: int = UserRole.USER.value,
) -> User:
    user = User(
        username=username,
        password_hash=get_password_hash("secret"),
        nickname=username,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_music_directly(
    db: AsyncSession,
    title: str = "TestSong",
    is_published: bool = True,
) -> Music:
    music = Music(
        title=title,
        is_published=is_published,
        file_url="https://oss.example.com/musics/test.mp3",
        cover_icon_url="https://oss.example.com/covers/icon.jpg",
    )
    db.add(music)
    await db.commit()
    await db.refresh(music)
    return music


async def _create_album_directly(
    db: AsyncSession,
    title: str = "TestAlbum",
    is_deleted: bool = False,
    cover_icon_url: str | None = None,
    cover_url: str | None = None,
) -> Album:
    album = Album(
        title=title,
        is_deleted=is_deleted,
        cover_icon_url=cover_icon_url,
        cover_url=cover_url,
    )
    db.add(album)
    await db.commit()
    await db.refresh(album)
    return album


async def _add_music_to_album_directly(
    db: AsyncSession,
    album_id: int,
    music_id: int,
    ordinal: int = 0,
) -> AlbumMusic:
    am = AlbumMusic(album_id=album_id, music_id=music_id, ordinal=ordinal)
    db.add(am)
    await db.commit()
    await db.refresh(am)
    return am


async def _get_first_emotion_tag(db: AsyncSession) -> EmotionTag:
    result = await db.execute(select(EmotionTag).limit(1))
    return result.scalar_one()


async def _get_first_interest_tag(db: AsyncSession) -> InterestTag:
    result = await db.execute(select(InterestTag).limit(1))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_oss_uploads(monkeypatch):
    """所有专辑测试自动 mock OSS 图片上传函数。"""

    async def fake_image_upload(*args, **kwargs):
        return "https://fake-oss.example.com/albums/cover.jpg"

    monkeypatch.setattr(
        "echomemory_backend.core.oss_client.upload_image_to_oss",
        fake_image_upload,
    )


# ---------------------------------------------------------------------------
# 核心场景测试（Red 阶段先覆盖）
# ---------------------------------------------------------------------------

class TestAdminCreateAlbum:
    """测试管理员创建专辑接口。"""

    async def test_create_album_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常创建专辑，包含封面上传和基础字段校验。"""
        admin = await _create_user(db_session, "admin_album", role=UserRole.ADMIN.value)

        resp = client.post(
            ADMIN_BASE_URL,
            headers=_auth_header(admin),
            data={
                "title": "MyAlbum",
                "description": "A test album",
                "source": "TestSource",
            },
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover": ("cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "MyAlbum"
        assert data["description"] == "A test album"
        assert data["source"] == "TestSource"
        assert data["cover_icon_url"] == "https://fake-oss.example.com/albums/cover.jpg"
        assert data["cover_url"] == "https://fake-oss.example.com/albums/cover.jpg"
        assert data["emotion_tags"] == []
        assert data["interest_tags"] == []


class TestPublicGetAlbum:
    """测试公开获取专辑详情接口。"""

    async def test_get_album_detail_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常获取专辑详情，返回 200 并包含专辑标题。"""
        album = await _create_album_directly(
            db_session,
            title="PublicAlbum",
            cover_icon_url="https://oss.example.com/albums/icon.jpg",
        )

        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "PublicAlbum"


class TestAdminSoftDeleteAlbum:
    """测试管理员软删除专辑接口。"""

    async def test_deleted_album_not_publicly_visible(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试软删除后专辑对公众不可见，返回 404。"""
        admin = await _create_user(db_session, "admin_del", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="ToDeleteAlbum")

        resp = client.delete(
            f"{ADMIN_BASE_URL}/{album.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 404


class TestAdminAddMusicToAlbum:
    """测试管理员向专辑添加歌曲接口。"""

    async def test_add_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常将歌曲加入专辑，详情中应包含该歌曲。"""
        admin = await _create_user(db_session, "admin_add_m", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumWithMusic")
        music = await _create_music_directly(db_session, title="SongInAlbum")

        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 201

        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        assert len(resp.json()["musics"]) == 1

    async def test_add_music_already_in_another_album(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试将已属于其他专辑的歌曲加入本专辑时返回 409 冲突。"""
        admin = await _create_user(db_session, "admin_conflict", role=UserRole.ADMIN.value)
        album_a = await _create_album_directly(db_session, title="AlbumA")
        album_b = await _create_album_directly(db_session, title="AlbumB")
        music = await _create_music_directly(db_session, title="ConflictSong")
        await _add_music_to_album_directly(db_session, album_a.id, music.id)

        resp = client.post(
            f"{ADMIN_BASE_URL}/{album_b.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    async def test_add_duplicate_music(self, client: TestClient, db_session: AsyncSession):
        """测试重复向专辑添加同一首歌曲时返回 409 冲突。"""
        admin = await _create_user(db_session, "admin_dup_m", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumDup")
        music = await _create_music_directly(db_session, title="DupSong")
        await _add_music_to_album_directly(db_session, album.id, music.id)

        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 409

    async def test_add_unpublished_music(self, client: TestClient, db_session: AsyncSession):
        """测试向专辑添加未发布的歌曲时返回 404。"""
        admin = await _create_user(db_session, "admin_unpub_m", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumUnpub")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404


class TestAlbumTagSync:
    """测试专辑标签同步逻辑（添加/移除歌曲时自动聚合标签）。"""

    async def test_add_music_syncs_tags_to_album(
        self, client: TestClient, db_session: AsyncSession
    ):
        """将带标签的歌曲加入空专辑，专辑应自动获得该歌曲的标签。"""
        admin = await _create_user(db_session, "admin_tag_sync", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="TagSyncAlbum")
        music = await _create_music_directly(db_session, title="TaggedSong")

        # 给音乐添加标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music.id, interest_tag_id=interest_tag.id))
        await db_session.commit()

        # 通过 API 将歌曲加入专辑
        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 201

        # 验证专辑详情中包含该歌曲的标签
        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        data = resp.json()
        emotion_tag_ids = {t["id"] for t in data["emotion_tags"]}
        interest_tag_ids = {t["id"] for t in data["interest_tags"]}
        assert emotion_tag.id in emotion_tag_ids
        assert interest_tag.id in interest_tag_ids

    async def test_remove_music_syncs_tags_on_album(
        self, client: TestClient, db_session: AsyncSession
    ):
        """从专辑移除歌曲后，专辑标签应清空。"""
        admin = await _create_user(db_session, "admin_tag_remove", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="TagRemoveAlbum")
        music = await _create_music_directly(db_session, title="TaggedSongToRemove")

        # 给音乐添加标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music.id, interest_tag_id=interest_tag.id))
        await db_session.commit()

        # 通过 API 加入专辑（触发标签同步）
        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 201
        # 确认专辑已有标签
        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.json()["emotion_tags"] != []

        # 通过 API 移除歌曲
        resp = client.delete(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 204

        # 验证专辑标签已清空
        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["emotion_tags"] == []
        assert data["interest_tags"] == []

    async def test_add_multiple_musics_dedup_tags(
        self, client: TestClient, db_session: AsyncSession
    ):
        """向专辑添加多首标签重叠的歌曲，专辑标签应去重。"""
        admin = await _create_user(db_session, "admin_dedup", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="DedupAlbum")
        music1 = await _create_music_directly(db_session, title="Song1")
        music2 = await _create_music_directly(db_session, title="Song2")

        # 两首歌共享同一个情感标签，各自有不同的兴趣标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag1 = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music1.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicEmotionTag(music_id=music2.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music1.id, interest_tag_id=interest_tag1.id))
        await db_session.commit()

        # 加入第一首歌
        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music1.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 201

        # 加入第二首歌
        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music2.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 201

        # 验证情感标签只出现一次（去重）
        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["emotion_tags"]) == 1
        assert data["emotion_tags"][0]["id"] == emotion_tag.id
        assert len(data["interest_tags"]) == 1


class TestAdminRemoveMusicFromAlbum:
    """测试管理员从专辑移除歌曲接口。"""

    async def test_remove_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常从专辑移除歌曲，详情中不再包含该歌曲。"""
        admin = await _create_user(db_session, "admin_remove_m", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumRemove")
        music = await _create_music_directly(db_session, title="SongToRemove")
        await _add_music_to_album_directly(db_session, album.id, music.id)

        resp = client.delete(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{album.id}")
        assert resp.status_code == 200
        assert resp.json()["musics"] == []

    async def test_remove_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        """测试从专辑移除不存在的歌曲时返回 404。"""
        admin = await _create_user(db_session, "admin_remove_nx", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumRemoveNx")

        resp = client.delete(
            f"{ADMIN_BASE_URL}/{album.id}/musics/99999",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404


class TestAdminUpdateAlbum:
    """测试管理员更新专辑信息接口。"""

    async def test_update_album_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常更新专辑标题、描述和来源，返回更新后的数据。"""
        admin = await _create_user(db_session, "admin_update_a", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="OldAlbumTitle")

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}",
            headers=_auth_header(admin),
            json={
                "title": "NewAlbumTitle",
                "description": "Updated description",
                "source": "UpdatedSource",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "NewAlbumTitle"
        assert data["description"] == "Updated description"
        assert data["source"] == "UpdatedSource"

    async def test_update_nonexistent_album(self, client: TestClient, db_session: AsyncSession):
        """测试更新不存在的专辑时返回 404。"""
        admin = await _create_user(db_session, "admin_update_nx", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{ADMIN_BASE_URL}/99999",
            headers=_auth_header(admin),
            json={"title": "GhostAlbum"},
        )
        assert resp.status_code == 404


class TestAdminCreateAlbumValidation:
    """测试管理员创建专辑时的参数校验与权限控制。"""

    async def test_create_missing_cover_icon(self, client: TestClient, db_session: AsyncSession):
        """测试缺少封面图标时创建专辑返回 422 校验错误。"""
        admin = await _create_user(db_session, "admin_no_icon", role=UserRole.ADMIN.value)

        resp = client.post(
            ADMIN_BASE_URL,
            headers=_auth_header(admin),
            data={"title": "NoIconAlbum"},
            files={
                "cover": ("cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 422

    async def test_create_invalid_cover_type(self, client: TestClient, db_session: AsyncSession):
        """测试上传非图片类型封面时返回 422 校验错误。"""
        admin = await _create_user(db_session, "admin_bad_cover", role=UserRole.ADMIN.value)

        resp = client.post(
            ADMIN_BASE_URL,
            headers=_auth_header(admin),
            data={"title": "BadCoverAlbum"},
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover": ("cover.exe", b"not an image", "application/octet-stream"),
            },
        )
        assert resp.status_code == 422

    async def test_normal_user_cannot_create(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限创建专辑时返回 403。"""
        user = await _create_user(db_session, "normal_create_a")

        resp = client.post(
            ADMIN_BASE_URL,
            headers=_auth_header(user),
            data={"title": "HackAlbum"},
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover": ("cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 403


class TestListAlbums:
    """测试专辑列表查询接口。"""

    async def test_list_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        """测试列表自动排除已软删除的专辑。"""
        await _create_album_directly(db_session, title="VisibleAlbum1")
        await _create_album_directly(db_session, title="VisibleAlbum2")
        await _create_album_directly(db_session, title="DeletedAlbum", is_deleted=True)

        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 200
        data = resp.json()
        titles = {a["title"] for a in data}
        assert "VisibleAlbum1" in titles
        assert "VisibleAlbum2" in titles
        assert "DeletedAlbum" not in titles

    async def test_list_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试专辑列表分页参数生效，返回指定数量结果。"""
        for i in range(5):
            await _create_album_directly(db_session, title=f"PaginatedAlbum{i}")

        resp = client.get(BASE_URL + "/", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestSearchAlbums:
    """测试专辑搜索接口。"""

    async def test_search_by_title(self, client: TestClient, db_session: AsyncSession):
        """测试按标题关键词搜索专辑，返回匹配结果。"""
        await _create_album_directly(db_session, title="Amazing Album")
        await _create_album_directly(db_session, title="Boring Album")

        resp = client.get(f"{BASE_URL}/search", params={"q": "Amazing"})
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        assert data["total"] == 1
        assert len(items) == 1
        assert items[0]["title"] == "Amazing Album"

    async def test_search_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        """测试搜索结果自动排除已软删除的专辑。"""
        await _create_album_directly(db_session, title="SearchableAlbum")
        await _create_album_directly(db_session, title="DeletedSearchAlbum", is_deleted=True)

        resp = client.get(f"{BASE_URL}/search", params={"q": "Search"})
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        titles = {a["title"] for a in items}
        assert "SearchableAlbum" in titles
        assert "DeletedSearchAlbum" not in titles


class TestAdminListAlbums:
    """测试管理员专辑列表接口。"""

    async def test_admin_list_success(self, client: TestClient, db_session: AsyncSession):
        """测试管理员列表正常返回专辑及作者、歌曲数信息。"""
        admin = await _create_user(db_session, "admin_list_a", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="ListAlbum")
        author = await _create_user(db_session, "album_author")
        music = await _create_music_directly(db_session, title="ListSong")
        # 添加作者和歌曲
        await _add_music_to_album_directly(db_session, album.id, music.id)
        from echomemory_backend.models.album import AlbumAuthor
        db_session.add(AlbumAuthor(album_id=album.id, author_id=author.id, ordinal=0))
        await db_session.commit()

        resp = client.get(f"{ADMIN_BASE_URL}/list", headers=_auth_header(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        item = next((a for a in data["items"] if a["id"] == album.id), None)
        assert item is not None
        assert item["title"] == "ListAlbum"
        assert item["music_count"] == 1
        assert len(item["authors"]) == 1
        assert item["authors"][0]["nickname"] == "album_author"

    async def test_admin_list_search(self, client: TestClient, db_session: AsyncSession):
        """测试管理员列表按标题搜索功能。"""
        admin = await _create_user(db_session, "admin_list_s", role=UserRole.ADMIN.value)
        await _create_album_directly(db_session, title="TargetAlbum")
        await _create_album_directly(db_session, title="OtherAlbum")

        resp = client.get(
            f"{ADMIN_BASE_URL}/list",
            headers=_auth_header(admin),
            params={"q": "Target"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "TargetAlbum"

    async def test_admin_list_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试管理员列表分页参数生效。"""
        admin = await _create_user(db_session, "admin_list_p", role=UserRole.ADMIN.value)
        for i in range(3):
            await _create_album_directly(db_session, title=f"PageAlbum{i}")

        resp = client.get(
            f"{ADMIN_BASE_URL}/list",
            headers=_auth_header(admin),
            params={"limit": 1, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 3

    async def test_admin_list_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        """测试管理员列表排除已软删除的专辑。"""
        admin = await _create_user(db_session, "admin_list_d", role=UserRole.ADMIN.value)
        await _create_album_directly(db_session, title="AliveAlbum")
        await _create_album_directly(db_session, title="DeletedAlbum", is_deleted=True)

        resp = client.get(f"{ADMIN_BASE_URL}/list", headers=_auth_header(admin))
        assert resp.status_code == 200
        data = resp.json()
        titles = {a["title"] for a in data["items"]}
        assert "AliveAlbum" in titles
        assert "DeletedAlbum" not in titles

    async def test_normal_user_cannot_list(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限访问管理员列表。"""
        user = await _create_user(db_session, "normal_list_a")
        resp = client.get(f"{ADMIN_BASE_URL}/list", headers=_auth_header(user))
        assert resp.status_code == 403


class TestAdminUpdateAlbumCovers:
    """测试管理员替换专辑封面接口。"""

    async def test_update_cover_icon(self, client: TestClient, db_session: AsyncSession):
        """测试单独替换封面图标成功。"""
        admin = await _create_user(db_session, "admin_cov_icon", role=UserRole.ADMIN.value)
        album = await _create_album_directly(
            db_session,
            title="CoverIconAlbum",
            cover_icon_url="https://oss.example.com/old_icon.jpg",
        )

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(admin),
            files={
                "cover_icon": ("new_icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_icon_url"] == "https://fake-oss.example.com/albums/cover.jpg"

    async def test_update_cover_image(self, client: TestClient, db_session: AsyncSession):
        """测试单独替换封面大图成功。"""
        admin = await _create_user(db_session, "admin_cov_img", role=UserRole.ADMIN.value)
        album = await _create_album_directly(
            db_session,
            title="CoverImgAlbum",
            cover_url="https://oss.example.com/old_cover.jpg",
        )

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(admin),
            files={
                "cover": ("new_cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_url"] == "https://fake-oss.example.com/albums/cover.jpg"

    async def test_update_both_covers(self, client: TestClient, db_session: AsyncSession):
        """测试同时替换封面图标和封面大图成功。"""
        admin = await _create_user(db_session, "admin_cov_both", role=UserRole.ADMIN.value)
        album = await _create_album_directly(
            db_session,
            title="CoverBothAlbum",
            cover_icon_url="https://oss.example.com/old_icon.jpg",
            cover_url="https://oss.example.com/old_cover.jpg",
        )

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(admin),
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover": ("cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cover_icon_url"] == "https://fake-oss.example.com/albums/cover.jpg"
        assert data["cover_url"] == "https://fake-oss.example.com/albums/cover.jpg"

    async def test_update_cover_no_file(self, client: TestClient, db_session: AsyncSession):
        """测试未提供任何封面文件时返回 422。"""
        admin = await _create_user(db_session, "admin_cov_none", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="CoverNoneAlbum")

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 422

    async def test_update_cover_invalid_type(self, client: TestClient, db_session: AsyncSession):
        """测试上传非图片类型封面时返回 422。"""
        admin = await _create_user(db_session, "admin_cov_bad", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="CoverBadAlbum")

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(admin),
            files={
                "cover_icon": ("icon.exe", b"not an image", "application/octet-stream"),
            },
        )
        assert resp.status_code == 422

    async def test_update_cover_nonexistent_album(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试为不存在的专辑替换封面时返回 404。"""
        admin = await _create_user(db_session, "admin_cov_nx", role=UserRole.ADMIN.value)

        resp = client.patch(
            f"{ADMIN_BASE_URL}/99999/covers",
            headers=_auth_header(admin),
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 404

    async def test_normal_user_cannot_update_covers(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试普通用户无权限替换封面。"""
        user = await _create_user(db_session, "normal_cov")
        album = await _create_album_directly(db_session, title="CoverPermAlbum")

        resp = client.patch(
            f"{ADMIN_BASE_URL}/{album.id}/covers",
            headers=_auth_header(user),
            files={
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 403
