"""歌单模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import EmotionTag, InterestTag
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/playlists"


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


async def _create_playlist_directly(
    db: AsyncSession,
    user_id: int,
    title: str = "TestPlaylist",
    is_private: bool = False,
    cover_icon_url: str | None = None,
) -> Playlist:
    playlist = Playlist(
        title=title,
        user_id=user_id,
        is_private=is_private,
        cover_icon_url=cover_icon_url,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def _add_music_to_playlist_directly(
    db: AsyncSession,
    playlist_id: int,
    music_id: int,
    ordinal: int = 0,
) -> PlaylistMusic:
    pm = PlaylistMusic(playlist_id=playlist_id, music_id=music_id, ordinal=ordinal)
    db.add(pm)
    await db.commit()
    await db.refresh(pm)
    return pm


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
    """所有歌单测试自动 mock OSS 图片上传函数。"""

    async def fake_image_upload(*args, **kwargs):
        return "https://fake-oss.example.com/playlists/cover.jpg"

    monkeypatch.setattr(
        "echomemory_backend.core.oss_client.upload_image_to_oss",
        fake_image_upload,
    )


# ---------------------------------------------------------------------------
# 创建歌单测试
# ---------------------------------------------------------------------------

class TestCreatePlaylist:
    async def test_create_playlist_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "create_pl_user")
        etag = await _get_first_emotion_tag(db_session)
        itag = await _get_first_interest_tag(db_session)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            data={
                "title": "MyPlaylist",
                "description": "A test playlist",
                "is_private": "false",
                "emotion_tag_ids": etag.id,
                "interest_tag_ids": itag.id,
            },
            files={
                "cover_icon": ("cover.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "MyPlaylist"
        assert data["description"] == "A test playlist"
        assert data["is_private"] is False
        assert data["cover_icon_url"] == "https://fake-oss.example.com/playlists/cover.jpg"
        assert len(data["emotion_tags"]) == 1
        assert len(data["interest_tags"]) == 1
        assert data["user"]["id"] == user.id

    async def test_create_playlist_without_cover(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "create_pl_nocover")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            data={"title": "NoCoverPlaylist"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "NoCoverPlaylist"
        assert data["cover_icon_url"] is None

    async def test_create_playlist_missing_title(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "create_pl_notitle")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            data={"description": "No title"},
        )
        assert resp.status_code == 422

    async def test_create_playlist_unauthorized(self, client: TestClient):
        resp = client.post(
            BASE_URL + "/",
            data={"title": "HackPlaylist"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 查询歌单列表测试
# ---------------------------------------------------------------------------

class TestListPlaylists:
    async def test_list_my_playlists(self, client: TestClient, db_session: AsyncSession):
        user_a = await _create_user(db_session, "list_pl_a")
        user_b = await _create_user(db_session, "list_pl_b")

        await _create_playlist_directly(db_session, user_a.id, title="PlaylistA1")
        await _create_playlist_directly(db_session, user_a.id, title="PlaylistA2")
        await _create_playlist_directly(db_session, user_b.id, title="PlaylistB1")

        resp = client.get(BASE_URL + "/", headers=_auth_header(user_a))
        assert resp.status_code == 200
        data = resp.json()
        titles = {p["title"] for p in data}
        assert "PlaylistA1" in titles
        assert "PlaylistA2" in titles
        assert "PlaylistB1" not in titles

    async def test_list_playlists_pagination(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_pl_page")
        for i in range(5):
            await _create_playlist_directly(db_session, user.id, title=f"Playlist{i}")

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ---------------------------------------------------------------------------
# 查询歌单详情测试
# ---------------------------------------------------------------------------

class TestGetPlaylist:
    async def test_get_own_playlist_detail(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "get_own")
        music = await _create_music_directly(db_session, title="SongInPlaylist")
        playlist = await _create_playlist_directly(db_session, user.id, title="OwnPlaylist")
        await _add_music_to_playlist_directly(db_session, playlist.id, music.id)

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "OwnPlaylist"
        assert data["user"]["id"] == user.id
        assert len(data["musics"]) == 1
        assert data["musics"][0]["music"]["title"] == "SongInPlaylist"

    async def test_get_public_playlist_detail(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "get_pub_owner")
        viewer = await _create_user(db_session, "get_pub_viewer")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="PublicPlaylist", is_private=False
        )

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(viewer))
        assert resp.status_code == 200
        assert resp.json()["title"] == "PublicPlaylist"

    async def test_get_private_playlist_of_others(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "get_priv_owner")
        viewer = await _create_user(db_session, "get_priv_viewer")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="PrivatePlaylist", is_private=True
        )

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(viewer))
        assert resp.status_code == 403

    async def test_get_nonexistent_playlist(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "get_nx")
        resp = client.get(f"{BASE_URL}/99999", headers=_auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 修改歌单测试
# ---------------------------------------------------------------------------

class TestUpdatePlaylist:
    async def test_update_playlist_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "update_own")
        playlist = await _create_playlist_directly(
            db_session, user.id, title="OldTitle", is_private=False
        )
        etag = await _get_first_emotion_tag(db_session)

        resp = client.patch(
            f"{BASE_URL}/{playlist.id}",
            headers=_auth_header(user),
            json={
                "title": "NewTitle",
                "description": "Updated desc",
                "is_private": True,
                "emotion_tag_ids": [etag.id],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "NewTitle"
        assert data["description"] == "Updated desc"
        assert data["is_private"] is True
        assert len(data["emotion_tags"]) == 1

    async def test_update_others_playlist(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "update_other_owner")
        hacker = await _create_user(db_session, "update_other_hacker")
        playlist = await _create_playlist_directly(db_session, owner.id, title="Protected")

        resp = client.patch(
            f"{BASE_URL}/{playlist.id}",
            headers=_auth_header(hacker),
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 删除歌单测试
# ---------------------------------------------------------------------------

class TestDeletePlaylist:
    async def test_delete_playlist_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "delete_own")
        playlist = await _create_playlist_directly(db_session, user.id, title="ToDelete")

        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 404

    async def test_delete_others_playlist(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "delete_other_owner")
        hacker = await _create_user(db_session, "delete_other_hacker")
        playlist = await _create_playlist_directly(db_session, owner.id, title="Protected")

        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(hacker))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 添加/移除歌曲测试
# ---------------------------------------------------------------------------

class TestAddRemoveMusic:
    async def test_add_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "add_music_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="AddMusicPL")
        music = await _create_music_directly(db_session, title="SongToAdd")

        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        # 验证歌单详情中已包含该歌曲
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert len(resp.json()["musics"]) == 1

    async def test_add_unpublished_music(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "add_unpub_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="AddUnpubPL")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_add_duplicate_music(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "add_dup_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="AddDupPL")
        music = await _create_music_directly(db_session, title="DupSong")
        await _add_music_to_playlist_directly(db_session, playlist.id, music.id)

        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 409

    async def test_add_music_to_others_playlist(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "add_other_owner")
        hacker = await _create_user(db_session, "add_other_hacker")
        playlist = await _create_playlist_directly(db_session, owner.id, title="ProtectedPL")
        music = await _create_music_directly(db_session, title="SongForOther")

        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(hacker),
        )
        assert resp.status_code == 403

    async def test_remove_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "remove_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="RemovePL")
        music = await _create_music_directly(db_session, title="SongToRemove")
        await _add_music_to_playlist_directly(db_session, playlist.id, music.id)

        resp = client.delete(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["musics"] == []

    async def test_remove_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "remove_nx_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="RemoveNxPL")

        resp = client.delete(
            f"{BASE_URL}/{playlist.id}/musics/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404
