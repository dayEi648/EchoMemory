"""播放历史模块测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/play-history"


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


async def _create_play_history_directly(
    db: AsyncSession,
    user_id: int,
    music_id: int,
    played_at: datetime | None = None,
) -> PlayHistory:
    history = PlayHistory(user_id=user_id, music_id=music_id)
    if played_at is not None:
        history.played_at = played_at
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


async def _create_album_directly(
    db: AsyncSession, title: str = "TestAlbum"
) -> Album:
    album = Album(title=title)
    db.add(album)
    await db.commit()
    await db.refresh(album)
    return album


async def _create_playlist_directly(
    db: AsyncSession, user_id: int, title: str = "TestPlaylist"
) -> Playlist:
    playlist = Playlist(title=title, user_id=user_id)
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def _add_music_to_album(
    db: AsyncSession, album_id: int, music_id: int, ordinal: int = 0
) -> None:
    db.add(AlbumMusic(album_id=album_id, music_id=music_id, ordinal=ordinal))
    await db.commit()


async def _add_music_to_playlist(
    db: AsyncSession, playlist_id: int, music_id: int, ordinal: int = 0
) -> None:
    db.add(PlaylistMusic(playlist_id=playlist_id, music_id=music_id, ordinal=ordinal))
    await db.commit()


# ---------------------------------------------------------------------------
# 记录播放测试
# ---------------------------------------------------------------------------

class TestRecordPlay:
    async def test_record_play_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "record_user")
        music = await _create_music_directly(db_session, title="PublishedSong")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["music"]["id"] == music.id
        assert data["music"]["title"] == music.title
        assert "played_at" in data

    async def test_record_play_increments_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "record_count")
        music = await _create_music_directly(db_session, title="CountSong")
        assert music.play_count == 0

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201

        # 重新加载音乐记录以验证播放次数递增
        result = await db_session.execute(select(Music).where(Music.id == music.id))
        updated_music = result.scalar_one()
        await db_session.refresh(updated_music)
        assert updated_music.play_count == 1

    async def test_record_play_increments_album_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "album_count")
        music = await _create_music_directly(db_session, title="AlbumSong")
        album = await _create_album_directly(db_session, title="MyAlbum")
        await _add_music_to_album(db_session, album.id, music.id)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201

        result = await db_session.execute(select(Album).where(Album.id == album.id))
        updated_album = result.scalar_one()
        await db_session.refresh(updated_album)
        assert updated_album.play_count == 1

    async def test_record_play_increments_playlist_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "playlist_count")
        music = await _create_music_directly(db_session, title="PlaylistSong")
        playlist = await _create_playlist_directly(db_session, user.id, title="MyPlaylist")
        await _add_music_to_playlist(db_session, playlist.id, music.id)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id, "playlist_id": playlist.id},
        )
        assert resp.status_code == 201

        result = await db_session.execute(select(Playlist).where(Playlist.id == playlist.id))
        updated_playlist = result.scalar_one()
        await db_session.refresh(updated_playlist)
        assert updated_playlist.play_count == 1

    async def test_record_play_with_nonexistent_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "playlist_nx")
        music = await _create_music_directly(db_session, title="PlaylistNxSong")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id, "playlist_id": 99999},
        )
        assert resp.status_code == 404

    async def test_record_play_with_music_not_in_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "playlist_not_in")
        music = await _create_music_directly(db_session, title="NotInPlaylistSong")
        playlist = await _create_playlist_directly(db_session, user.id, title="EmptyPlaylist")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id, "playlist_id": playlist.id},
        )
        assert resp.status_code == 400

    async def test_record_play_unpublished_music(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "record_unpub")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 404

    async def test_record_play_nonexistent_music(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "record_nx")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": 99999},
        )
        assert resp.status_code == 404

    async def test_record_play_unauthorized(self, client: TestClient, db_session: AsyncSession):
        music = await _create_music_directly(db_session)

        resp = client.post(
            BASE_URL + "/",
            json={"music_id": music.id},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 查询播放历史测试
# ---------------------------------------------------------------------------

class TestListPlayHistory:
    async def test_list_play_history_order(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "list_order")
        music = await _create_music_directly(db_session, title="SongOrder")

        now = datetime.now(timezone.utc)
        await _create_play_history_directly(
            db_session, user.id, music.id, played_at=now - timedelta(hours=2)
        )
        await _create_play_history_directly(
            db_session, user.id, music.id, played_at=now - timedelta(hours=1)
        )
        await _create_play_history_directly(
            db_session, user.id, music.id, played_at=now
        )

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # 验证倒序：最新的在前
        t0 = datetime.fromisoformat(data[0]["played_at"])
        t1 = datetime.fromisoformat(data[1]["played_at"])
        t2 = datetime.fromisoformat(data[2]["played_at"])
        assert t0 >= t1 >= t2

    async def test_list_play_history_pagination(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "list_page")
        music = await _create_music_directly(db_session, title="SongPage")

        for i in range(5):
            await _create_play_history_directly(db_session, user.id, music.id)

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

    async def test_list_play_history_only_own(
        self, client: TestClient, db_session: AsyncSession
    ):
        user_a = await _create_user(db_session, "list_own_a")
        user_b = await _create_user(db_session, "list_own_b")
        music = await _create_music_directly(db_session, title="SongOwn")

        await _create_play_history_directly(db_session, user_a.id, music.id)
        await _create_play_history_directly(db_session, user_b.id, music.id)

        resp = client.get(BASE_URL + "/", headers=_auth_header(user_a))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    async def test_list_play_history_unauthorized(self, client: TestClient):
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 删除播放历史测试
# ---------------------------------------------------------------------------

class TestDeletePlayHistory:
    async def test_delete_single_history(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "delete_single")
        music = await _create_music_directly(db_session, title="SongDelete")
        history = await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.delete(
            f"{BASE_URL}/{history.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        # 再次查询应为空
        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_delete_others_history(
        self, client: TestClient, db_session: AsyncSession
    ):
        user_a = await _create_user(db_session, "delete_other_a")
        user_b = await _create_user(db_session, "delete_other_b")
        music = await _create_music_directly(db_session, title="SongOther")
        history = await _create_play_history_directly(db_session, user_a.id, music.id)

        resp = client.delete(
            f"{BASE_URL}/{history.id}",
            headers=_auth_header(user_b),
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_history(
        self, client: TestClient, db_session: AsyncSession
    ):
        user = await _create_user(db_session, "delete_nx")

        resp = client.delete(
            f"{BASE_URL}/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 清空播放历史测试
# ---------------------------------------------------------------------------

class TestClearPlayHistory:
    async def test_clear_history(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "clear_user")
        music = await _create_music_directly(db_session, title="SongClear")

        for _ in range(3):
            await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.delete(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 204

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_clear_history_unauthorized(self, client: TestClient):
        resp = client.delete(BASE_URL + "/")
        assert resp.status_code == 401
