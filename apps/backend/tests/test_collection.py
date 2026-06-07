"""收藏模块测试 —— TDD：先写测试，再写实现。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/collections"


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
) -> Album:
    album = Album(
        title=title,
        cover_icon_url="https://oss.example.com/albums/icon.jpg",
        cover_url="https://oss.example.com/albums/cover.jpg",
        is_deleted=is_deleted,
    )
    db.add(album)
    await db.commit()
    await db.refresh(album)
    return album


async def _create_playlist_directly(
    db: AsyncSession,
    user_id: int,
    title: str = "TestPlaylist",
    is_private: bool = False,
) -> Playlist:
    playlist = Playlist(
        title=title,
        user_id=user_id,
        is_private=is_private,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


# ============================================================================
# 音乐收藏
# ============================================================================


class TestCollectMusic:
    async def test_collect_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_music_user")
        music = await _create_music_directly(db_session, title="SongToCollect")

        resp = client.post(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["music"]["id"] == music.id
        assert data["music"]["title"] == "SongToCollect"
        assert "created_at" in data

    async def test_collect_music_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_music_idem")
        music = await _create_music_directly(db_session, title="SongIdem")

        resp = client.post(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        # 验证数据库只有一条记录
        result = await db_session.execute(
            select(UserMusicCollection).where(
                UserMusicCollection.user_id == user.id,
                UserMusicCollection.music_id == music.id,
            )
        )
        assert len(result.scalars().all()) == 1

    async def test_collect_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_music_nx")

        resp = client.post(
            f"{BASE_URL}/musics/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        music = await _create_music_directly(db_session, title="SongUnauth")

        resp = client.post(f"{BASE_URL}/musics/{music.id}")
        assert resp.status_code == 401


class TestUncollectMusic:
    async def test_uncollect_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_music_user")
        music = await _create_music_directly(db_session, title="SongToUncollect")

        # 先收藏
        client.post(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )

        resp = client.delete(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        # 验证数据库无记录
        result = await db_session.execute(
            select(UserMusicCollection).where(
                UserMusicCollection.user_id == user.id,
                UserMusicCollection.music_id == music.id,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_uncollect_music_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_music_idem")
        music = await _create_music_directly(db_session, title="SongNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

    async def test_uncollect_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        music = await _create_music_directly(db_session, title="SongUnauthUncollect")

        resp = client.delete(f"{BASE_URL}/musics/{music.id}")
        assert resp.status_code == 401


class TestListMusicCollections:
    async def test_list_music_collections(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_music_user")
        music1 = await _create_music_directly(db_session, title="Song1")
        music2 = await _create_music_directly(db_session, title="Song2")

        client.post(f"{BASE_URL}/musics/{music1.id}", headers=_auth_header(user))
        client.post(f"{BASE_URL}/musics/{music2.id}", headers=_auth_header(user))

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {item["music"]["title"] for item in data}
        assert "Song1" in titles
        assert "Song2" in titles

    async def test_list_music_collections_empty(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_music_empty")

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_music_collections_pagination(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_music_page")
        for i in range(5):
            music = await _create_music_directly(db_session, title=f"SongPage{i}")
            client.post(f"{BASE_URL}/musics/{music.id}", headers=_auth_header(user))

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_list_music_collections_other_user(self, client: TestClient, db_session: AsyncSession):
        user_a = await _create_user(db_session, "list_music_a")
        user_b = await _create_user(db_session, "list_music_b")
        music = await _create_music_directly(db_session, title="SongPrivate")

        client.post(f"{BASE_URL}/musics/{music.id}", headers=_auth_header(user_a))

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user_b),
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# 专辑收藏
# ============================================================================


class TestCollectAlbum:
    async def test_collect_album_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_album_user")
        album = await _create_album_directly(db_session, title="AlbumToCollect")

        resp = client.post(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["album"]["id"] == album.id
        assert data["album"]["title"] == "AlbumToCollect"

    async def test_collect_album_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_album_idem")
        album = await _create_album_directly(db_session, title="AlbumIdem")

        resp = client.post(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

    async def test_collect_nonexistent_album(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_album_nx")

        resp = client.post(
            f"{BASE_URL}/albums/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_deleted_album(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_album_del")
        album = await _create_album_directly(db_session, title="AlbumDeleted", is_deleted=True)

        resp = client.post(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_album_unauthorized(self, client: TestClient, db_session: AsyncSession):
        album = await _create_album_directly(db_session, title="AlbumUnauth")

        resp = client.post(f"{BASE_URL}/albums/{album.id}")
        assert resp.status_code == 401


class TestUncollectAlbum:
    async def test_uncollect_album_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_album_user")
        album = await _create_album_directly(db_session, title="AlbumToUncollect")

        client.post(f"{BASE_URL}/albums/{album.id}", headers=_auth_header(user))

        resp = client.delete(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

    async def test_uncollect_album_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_album_idem")
        album = await _create_album_directly(db_session, title="AlbumNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListAlbumCollections:
    async def test_list_album_collections(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_album_user")
        album1 = await _create_album_directly(db_session, title="Album1")
        album2 = await _create_album_directly(db_session, title="Album2")

        client.post(f"{BASE_URL}/albums/{album1.id}", headers=_auth_header(user))
        client.post(f"{BASE_URL}/albums/{album2.id}", headers=_auth_header(user))

        resp = client.get(
            f"{BASE_URL}/albums",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {item["album"]["title"] for item in data}
        assert "Album1" in titles
        assert "Album2" in titles

    async def test_list_album_collections_empty(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_album_empty")

        resp = client.get(
            f"{BASE_URL}/albums",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# 歌单收藏
# ============================================================================


class TestCollectPlaylist:
    async def test_collect_playlist_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_pl_user")
        owner = await _create_user(db_session, "collect_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistToCollect")

        resp = client.post(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["playlist"]["id"] == playlist.id
        assert data["playlist"]["title"] == "PlaylistToCollect"
        assert data["playlist"]["user"]["id"] == owner.id

    async def test_collect_playlist_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_pl_idem")
        owner = await _create_user(db_session, "collect_pl_idem_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistIdem")

        resp = client.post(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

    async def test_collect_nonexistent_playlist(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "collect_pl_nx")

        resp = client.post(
            f"{BASE_URL}/playlists/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_playlist_unauthorized(self, client: TestClient, db_session: AsyncSession):
        owner = await _create_user(db_session, "collect_pl_unauth_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistUnauth")

        resp = client.post(f"{BASE_URL}/playlists/{playlist.id}")
        assert resp.status_code == 401


class TestUncollectPlaylist:
    async def test_uncollect_playlist_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_pl_user")
        owner = await _create_user(db_session, "uncollect_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistToUncollect")

        client.post(f"{BASE_URL}/playlists/{playlist.id}", headers=_auth_header(user))

        resp = client.delete(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

    async def test_uncollect_playlist_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "uncollect_pl_idem")
        owner = await _create_user(db_session, "uncollect_pl_idem_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListPlaylistCollections:
    async def test_list_playlist_collections(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_pl_user")
        owner = await _create_user(db_session, "list_pl_owner")
        playlist1 = await _create_playlist_directly(db_session, owner.id, title="Playlist1")
        playlist2 = await _create_playlist_directly(db_session, owner.id, title="Playlist2")

        client.post(f"{BASE_URL}/playlists/{playlist1.id}", headers=_auth_header(user))
        client.post(f"{BASE_URL}/playlists/{playlist2.id}", headers=_auth_header(user))

        resp = client.get(
            f"{BASE_URL}/playlists",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {item["playlist"]["title"] for item in data}
        assert "Playlist1" in titles
        assert "Playlist2" in titles

    async def test_list_playlist_collections_empty(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_pl_empty")

        resp = client.get(
            f"{BASE_URL}/playlists",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert resp.json() == []


# ============================================================================
# 已发布音乐标记
# ============================================================================


class TestReleaseMusic:
    async def test_release_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "release_music_user")
        music = await _create_music_directly(db_session, title="SongToRelease")

        resp = client.post(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["music"]["id"] == music.id
        assert data["music"]["title"] == "SongToRelease"

    async def test_release_music_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "release_music_idem")
        music = await _create_music_directly(db_session, title="SongReleaseIdem")

        resp = client.post(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        resp = client.post(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        result = await db_session.execute(
            select(UserMusicRelease).where(
                UserMusicRelease.user_id == user.id,
                UserMusicRelease.music_id == music.id,
            )
        )
        assert len(result.scalars().all()) == 1

    async def test_release_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "release_music_nx")

        resp = client.post(
            f"{BASE_URL}/releases/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_release_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        music = await _create_music_directly(db_session, title="SongReleaseUnauth")

        resp = client.post(f"{BASE_URL}/releases/{music.id}")
        assert resp.status_code == 401


class TestUnreleaseMusic:
    async def test_unrelease_music_success(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "unrelease_music_user")
        music = await _create_music_directly(db_session, title="SongToUnrelease")

        client.post(f"{BASE_URL}/releases/{music.id}", headers=_auth_header(user))

        resp = client.delete(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        result = await db_session.execute(
            select(UserMusicRelease).where(
                UserMusicRelease.user_id == user.id,
                UserMusicRelease.music_id == music.id,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_unrelease_music_idempotent(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "unrelease_music_idem")
        music = await _create_music_directly(db_session, title="SongNeverReleased")

        resp = client.delete(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListReleases:
    async def test_list_releases(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_release_user")
        music1 = await _create_music_directly(db_session, title="ReleaseSong1")
        music2 = await _create_music_directly(db_session, title="ReleaseSong2")

        client.post(f"{BASE_URL}/releases/{music1.id}", headers=_auth_header(user))
        client.post(f"{BASE_URL}/releases/{music2.id}", headers=_auth_header(user))

        resp = client.get(
            f"{BASE_URL}/releases",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {item["music"]["title"] for item in data}
        assert "ReleaseSong1" in titles
        assert "ReleaseSong2" in titles

    async def test_list_releases_empty(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "list_release_empty")

        resp = client.get(
            f"{BASE_URL}/releases",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        assert resp.json() == []
