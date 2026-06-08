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
from echomemory_backend.models.music import Music
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
    async def test_create_album_success(self, client: TestClient, db_session: AsyncSession):
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
    async def test_get_album_detail_success(self, client: TestClient, db_session: AsyncSession):
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
    async def test_deleted_album_not_publicly_visible(
        self, client: TestClient, db_session: AsyncSession
    ):
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
    async def test_add_music_success(self, client: TestClient, db_session: AsyncSession):
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
        admin = await _create_user(db_session, "admin_unpub_m", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumUnpub")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            f"{ADMIN_BASE_URL}/{album.id}/musics/{music.id}",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404


class TestAdminRemoveMusicFromAlbum:
    async def test_remove_music_success(self, client: TestClient, db_session: AsyncSession):
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
        admin = await _create_user(db_session, "admin_remove_nx", role=UserRole.ADMIN.value)
        album = await _create_album_directly(db_session, title="AlbumRemoveNx")

        resp = client.delete(
            f"{ADMIN_BASE_URL}/{album.id}/musics/99999",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 404


class TestAdminUpdateAlbum:
    async def test_update_album_success(self, client: TestClient, db_session: AsyncSession):
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
        admin = await _create_user(db_session, "admin_update_nx", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{ADMIN_BASE_URL}/99999",
            headers=_auth_header(admin),
            json={"title": "GhostAlbum"},
        )
        assert resp.status_code == 404


class TestAdminCreateAlbumValidation:
    async def test_create_missing_cover_icon(self, client: TestClient, db_session: AsyncSession):
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
    async def test_list_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
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
        for i in range(5):
            await _create_album_directly(db_session, title=f"PaginatedAlbum{i}")

        resp = client.get(BASE_URL + "/", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestSearchAlbums:
    async def test_search_by_title(self, client: TestClient, db_session: AsyncSession):
        await _create_album_directly(db_session, title="Amazing Album")
        await _create_album_directly(db_session, title="Boring Album")

        resp = client.get(f"{BASE_URL}/search", params={"q": "Amazing"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Amazing Album"

    async def test_search_excludes_deleted(self, client: TestClient, db_session: AsyncSession):
        await _create_album_directly(db_session, title="SearchableAlbum")
        await _create_album_directly(db_session, title="DeletedSearchAlbum", is_deleted=True)

        resp = client.get(f"{BASE_URL}/search", params={"q": "Search"})
        assert resp.status_code == 200
        data = resp.json()
        titles = {a["title"] for a in data}
        assert "SearchableAlbum" in titles
        assert "DeletedSearchAlbum" not in titles
