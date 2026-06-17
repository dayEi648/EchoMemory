"""播放历史模块测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User
from tests.api_helpers import api_data

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
    play_count: int = 1,
) -> PlayHistory:
    history = PlayHistory(user_id=user_id, music_id=music_id, play_count=play_count)
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
    """测试记录播放功能。"""

    async def test_record_play_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常记录播放历史。"""
        user = await _create_user(db_session, "record_user")
        music = await _create_music_directly(db_session, title="PublishedSong")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201
        data = api_data(resp)
        assert data["music"]["id"] == music.id
        assert data["music"]["title"] == music.title
        assert "played_at" in data

    async def test_record_play_replays_increment_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试重复播放同一音乐时 play_count 递增且保持同一条记录。"""
        user = await _create_user(db_session, "record_replay")
        music = await _create_music_directly(db_session, title="ReplaySong")

        first_resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert first_resp.status_code == 201
        first_id = api_data(first_resp)["id"]
        assert api_data(first_resp)["play_count"] == 1

        second_resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert second_resp.status_code == 201
        second_id = api_data(second_resp)["id"]
        assert api_data(second_resp)["play_count"] == 2

        assert second_id == first_id

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == first_id
        assert data["items"][0]["music"]["id"] == music.id
        assert data["items"][0]["play_count"] == 2

        result = await db_session.execute(
            select(PlayHistory).where(
                PlayHistory.user_id == user.id,
                PlayHistory.music_id == music.id,
            )
        )
        histories = list(result.scalars().all())
        assert len(histories) == 1
        assert histories[0].play_count == 2

    async def test_record_play_keeps_latest_100_items(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试新增播放历史后仅保留用户最近 100 条记录。"""
        user = await _create_user(db_session, "record_limit")
        now = datetime.now(timezone.utc)
        first_music: Music | None = None

        for i in range(100):
            music = await _create_music_directly(db_session, title=f"LimitSong{i}")
            if first_music is None:
                first_music = music
            await _create_play_history_directly(
                db_session,
                user.id,
                music.id,
                played_at=now + timedelta(seconds=i),
            )

        new_music = await _create_music_directly(db_session, title="LimitNewestSong")
        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": new_music.id},
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(PlayHistory).where(PlayHistory.user_id == user.id)
        )
        histories = list(result.scalars().all())
        music_ids = {history.music_id for history in histories}
        assert len(histories) == 100
        assert first_music is not None
        assert first_music.id not in music_ids
        assert new_music.id in music_ids

    async def test_record_play_increments_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试记录播放时歌曲播放次数递增。"""
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

    async def test_record_play_increments_existing_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试重复播放时，已有的 play_count 会继续递增。"""
        user = await _create_user(db_session, "record_existing_count")
        music = await _create_music_directly(db_session, title="ExistingCountSong")
        history = await _create_play_history_directly(
            db_session, user.id, music.id, play_count=3
        )
        assert history.play_count == 3

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201
        assert api_data(resp)["play_count"] == 4

        result = await db_session.execute(
            select(PlayHistory).where(
                PlayHistory.user_id == user.id,
                PlayHistory.music_id == music.id,
            )
        )
        updated_history = result.scalar_one()
        await db_session.refresh(updated_history)
        assert updated_history.play_count == 4

    async def test_record_play_increments_album_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试记录播放时专辑播放次数递增。"""
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
        """测试记录播放时歌单播放次数递增。"""
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
        """测试使用不存在的歌单 ID 记录播放时返回 404。"""
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
        """测试记录不在歌单中的歌曲播放时返回 400。"""
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
        """测试对未发布音乐记录播放时返回 404。"""
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
        """测试对不存在的音乐记录播放时返回 404。"""
        user = await _create_user(db_session, "record_nx")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            json={"music_id": 99999},
        )
        assert resp.status_code == 404

    async def test_record_play_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户记录播放时返回 401。"""
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
    """测试查询播放历史功能。"""

    async def test_list_play_history_includes_play_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试播放历史列表返回中包含 play_count。"""
        user = await _create_user(db_session, "list_play_count")
        music = await _create_music_directly(db_session, title="ListCountSong")
        await _create_play_history_directly(
            db_session, user.id, music.id, play_count=5
        )

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["play_count"] == 5

    async def test_list_play_history_order(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试播放历史按时间倒序返回。"""
        user = await _create_user(db_session, "list_order")
        musics = [
            await _create_music_directly(db_session, title=f"SongOrder{i}")
            for i in range(3)
        ]

        now = datetime.now(timezone.utc)
        await _create_play_history_directly(
            db_session, user.id, musics[0].id, played_at=now - timedelta(hours=2)
        )
        await _create_play_history_directly(
            db_session, user.id, musics[1].id, played_at=now - timedelta(hours=1)
        )
        await _create_play_history_directly(
            db_session, user.id, musics[2].id, played_at=now
        )

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # 验证倒序：最新的在前
        t0 = datetime.fromisoformat(data["items"][0]["played_at"])
        t1 = datetime.fromisoformat(data["items"][1]["played_at"])
        t2 = datetime.fromisoformat(data["items"][2]["played_at"])
        assert t0 >= t1 >= t2

    async def test_list_play_history_pagination(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试播放历史分页查询。"""
        user = await _create_user(db_session, "list_page")

        for i in range(5):
            music = await _create_music_directly(db_session, title=f"SongPage{i}")
            await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        assert api_data(resp)["total"] == 5
        assert len(api_data(resp)["items"]) == 2

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        assert len(api_data(resp)["items"]) == 2

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        assert len(api_data(resp)["items"]) == 1

    async def test_list_play_history_only_own(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试用户只能查看自己的播放历史。"""
        user_a = await _create_user(db_session, "list_own_a")
        user_b = await _create_user(db_session, "list_own_b")
        music = await _create_music_directly(db_session, title="SongOwn")

        await _create_play_history_directly(db_session, user_a.id, music.id)
        await _create_play_history_directly(db_session, user_b.id, music.id)

        resp = client.get(BASE_URL + "/", headers=_auth_header(user_a))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_list_play_history_unauthorized(self, client: TestClient):
        """测试未登录用户查询播放历史时返回 401。"""
        resp = client.get(BASE_URL + "/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 删除播放历史测试
# ---------------------------------------------------------------------------

class TestDeletePlayHistory:
    """测试删除播放历史功能。"""

    async def test_delete_single_history(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试正常删除单条播放历史。"""
        user = await _create_user(db_session, "delete_single")
        music = await _create_music_directly(db_session, title="SongDelete")
        history = await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.delete(
            f"{BASE_URL}/{history.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert api_data(resp) is None

        # 再次查询应为空
        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_delete_others_history(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试删除他人播放历史时返回 404。"""
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
        """测试删除不存在的播放历史时返回 404。"""
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
    """测试清空播放历史功能。"""

    async def test_clear_history(self, client: TestClient, db_session: AsyncSession):
        """测试正常清空当前用户的播放历史。"""
        user = await _create_user(db_session, "clear_user")

        for i in range(3):
            music = await _create_music_directly(db_session, title=f"SongClear{i}")
            await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.delete(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        assert api_data(resp) is None

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 0
        assert data["items"] == []

    async def test_clear_history_unauthorized(self, client: TestClient):
        """测试未登录用户清空播放历史时返回 401。"""
        resp = client.delete(BASE_URL + "/")
        assert resp.status_code == 401

    async def test_list_play_history_includes_music_authors(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试播放历史列表正确返回音乐作者信息。"""
        user = await _create_user(db_session, "history_author_user")
        music = await _create_music_directly(db_session, title="SongWithAuthors")
        author = await _create_user(db_session, "history_author")
        db_session.add(
            MusicAuthor(music_id=music.id, author_id=author.id, ordinal=1)
        )
        await db_session.commit()
        await _create_play_history_directly(db_session, user.id, music.id)

        resp = client.get(BASE_URL + "/", headers=_auth_header(user))
        assert resp.status_code == 200
        data = api_data(resp)
        assert data["total"] == 1
        authors = data["items"][0]["music"]["authors"]
        assert len(authors) == 1
        assert authors[0]["id"] == author.id
        assert authors[0]["nickname"] == author.nickname
        assert authors[0]["username"] == author.username
