"""收藏模块测试 —— TDD：先写测试，再写实现。"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
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
    """测试音乐收藏功能。"""

    async def test_collect_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常收藏音乐。"""
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
        """测试重复收藏音乐的幂等性。"""
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

        # 验证歌曲只存在于用户的一个歌单中（默认喜欢歌单）
        result = await db_session.execute(
            select(PlaylistMusic)
            .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
            .where(
                Playlist.user_id == user.id,
                PlaylistMusic.music_id == music.id,
            )
        )
        assert len(result.scalars().all()) == 1

    async def test_collect_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        """测试收藏不存在的音乐时返回 404。"""
        user = await _create_user(db_session, "collect_music_nx")

        resp = client.post(
            f"{BASE_URL}/musics/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_unpublished_music(self, client: TestClient, db_session: AsyncSession):
        """测试收藏未发布的音乐时返回 404。"""
        user = await _create_user(db_session, "collect_unpub_music")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户收藏音乐时返回 401。"""
        music = await _create_music_directly(db_session, title="SongUnauth")

        resp = client.post(f"{BASE_URL}/musics/{music.id}")
        assert resp.status_code == 401


class TestUncollectMusic:
    """测试取消音乐收藏功能。"""

    async def test_uncollect_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消音乐收藏。"""
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

        # 验证歌曲已从用户全部歌单中移除
        result = await db_session.execute(
            select(PlaylistMusic)
            .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
            .where(
                Playlist.user_id == user.id,
                PlaylistMusic.music_id == music.id,
            )
        )
        assert len(result.scalars().all()) == 0

    async def test_uncollect_music_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试取消未收藏音乐的幂等性。"""
        user = await _create_user(db_session, "uncollect_music_idem")
        music = await _create_music_directly(db_session, title="SongNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

    async def test_uncollect_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户取消收藏时返回 401。"""
        music = await _create_music_directly(db_session, title="SongUnauthUncollect")

        resp = client.delete(f"{BASE_URL}/musics/{music.id}")
        assert resp.status_code == 401


class TestListMusicCollections:
    """测试音乐收藏列表查询功能。"""

    async def test_list_music_collections(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询音乐收藏列表。"""
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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        titles = {item["music"]["title"] for item in data["items"]}
        assert "Song1" in titles
        assert "Song2" in titles

    async def test_list_music_collections_empty(self, client: TestClient, db_session: AsyncSession):
        """测试无收藏记录时返回空列表。"""
        user = await _create_user(db_session, "list_music_empty")

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_music_collections_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试音乐收藏列表的分页查询。"""
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
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 1

    async def test_list_music_collections_other_user(self, client: TestClient, db_session: AsyncSession):
        """测试用户只能查看自己的音乐收藏。"""
        user_a = await _create_user(db_session, "list_music_a")
        user_b = await _create_user(db_session, "list_music_b")
        music = await _create_music_directly(db_session, title="SongPrivate")

        client.post(f"{BASE_URL}/musics/{music.id}", headers=_auth_header(user_a))

        resp = client.get(
            f"{BASE_URL}/musics",
            headers=_auth_header(user_b),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ============================================================================
# 专辑收藏
# ============================================================================


class TestCollectAlbum:
    """测试专辑收藏功能。"""

    async def test_collect_album_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常收藏专辑。"""
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
        """测试重复收藏专辑的幂等性。"""
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
        """测试收藏不存在的专辑时返回 404。"""
        user = await _create_user(db_session, "collect_album_nx")

        resp = client.post(
            f"{BASE_URL}/albums/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_deleted_album(self, client: TestClient, db_session: AsyncSession):
        """测试收藏已删除的专辑时返回 404。"""
        user = await _create_user(db_session, "collect_album_del")
        album = await _create_album_directly(db_session, title="AlbumDeleted", is_deleted=True)

        resp = client.post(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_album_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户收藏专辑时返回 401。"""
        album = await _create_album_directly(db_session, title="AlbumUnauth")

        resp = client.post(f"{BASE_URL}/albums/{album.id}")
        assert resp.status_code == 401


class TestUncollectAlbum:
    """测试取消专辑收藏功能。"""

    async def test_uncollect_album_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消专辑收藏。"""
        user = await _create_user(db_session, "uncollect_album_user")
        album = await _create_album_directly(db_session, title="AlbumToUncollect")

        client.post(f"{BASE_URL}/albums/{album.id}", headers=_auth_header(user))

        resp = client.delete(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

    async def test_uncollect_album_idempotent(self, client: TestClient, db_session: AsyncSession):
        """测试取消未收藏专辑的幂等性。"""
        user = await _create_user(db_session, "uncollect_album_idem")
        album = await _create_album_directly(db_session, title="AlbumNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/albums/{album.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListAlbumCollections:
    """测试专辑收藏列表查询功能。"""

    async def test_list_album_collections(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询专辑收藏列表。"""
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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        titles = {item["album"]["title"] for item in data["items"]}
        assert "Album1" in titles
        assert "Album2" in titles

    async def test_list_album_collections_empty(self, client: TestClient, db_session: AsyncSession):
        """测试无收藏记录时返回空列表。"""
        user = await _create_user(db_session, "list_album_empty")

        resp = client.get(
            f"{BASE_URL}/albums",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ============================================================================
# 歌单收藏
# ============================================================================


class TestCollectPlaylist:
    """测试歌单收藏功能。"""

    async def test_collect_playlist_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常收藏歌单。"""
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
        """测试重复收藏歌单的幂等性。"""
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
        """测试收藏不存在的歌单时返回 404。"""
        user = await _create_user(db_session, "collect_pl_nx")

        resp = client.post(
            f"{BASE_URL}/playlists/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_private_playlist(self, client: TestClient, db_session: AsyncSession):
        """测试收藏私密歌单时返回 404。"""
        user = await _create_user(db_session, "collect_private_pl")
        owner = await _create_user(db_session, "collect_private_pl_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PrivatePlaylist", is_private=True)

        resp = client.post(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_collect_own_playlist_forbidden(self, client: TestClient, db_session: AsyncSession):
        """测试收藏自己的歌单时返回 403。"""
        user = await _create_user(db_session, "collect_own_pl")
        playlist = await _create_playlist_directly(db_session, user.id, title="MyPlaylist")

        resp = client.post(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403

    async def test_collect_playlist_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户收藏歌单时返回 401。"""
        owner = await _create_user(db_session, "collect_pl_unauth_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistUnauth")

        resp = client.post(f"{BASE_URL}/playlists/{playlist.id}")
        assert resp.status_code == 401


class TestUncollectPlaylist:
    """测试取消歌单收藏功能。"""

    async def test_uncollect_playlist_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消歌单收藏。"""
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
        """测试取消未收藏歌单的幂等性。"""
        user = await _create_user(db_session, "uncollect_pl_idem")
        owner = await _create_user(db_session, "uncollect_pl_idem_owner")
        playlist = await _create_playlist_directly(db_session, owner.id, title="PlaylistNeverCollected")

        resp = client.delete(
            f"{BASE_URL}/playlists/{playlist.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListPlaylistCollections:
    """测试歌单收藏列表查询功能。"""

    async def test_list_playlist_collections(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询歌单收藏列表。"""
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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        titles = {item["playlist"]["title"] for item in data["items"]}
        assert "Playlist1" in titles
        assert "Playlist2" in titles

    async def test_list_playlist_collections_empty(self, client: TestClient, db_session: AsyncSession):
        """测试无收藏记录时返回空列表。"""
        user = await _create_user(db_session, "list_pl_empty")

        resp = client.get(
            f"{BASE_URL}/playlists",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# ============================================================================
# 已发布音乐标记
# ============================================================================


class TestReleaseMusic:
    """测试音乐发布标记功能。"""

    async def test_release_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常标记音乐为已发布。"""
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
        """测试重复标记音乐发布的幂等性。"""
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
        """测试标记不存在的音乐时返回 404。"""
        user = await _create_user(db_session, "release_music_nx")

        resp = client.post(
            f"{BASE_URL}/releases/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_release_music_unauthorized(self, client: TestClient, db_session: AsyncSession):
        """测试未登录用户标记发布时返回 401。"""
        music = await _create_music_directly(db_session, title="SongReleaseUnauth")

        resp = client.post(f"{BASE_URL}/releases/{music.id}")
        assert resp.status_code == 401


class TestUnreleaseMusic:
    """测试取消音乐发布标记功能。"""

    async def test_unrelease_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常取消音乐发布标记。"""
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
        """测试取消未发布标记的幂等性。"""
        user = await _create_user(db_session, "unrelease_music_idem")
        music = await _create_music_directly(db_session, title="SongNeverReleased")

        resp = client.delete(
            f"{BASE_URL}/releases/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204


class TestListReleases:
    """测试已发布音乐列表查询功能。"""

    async def test_list_releases(self, client: TestClient, db_session: AsyncSession):
        """测试正常查询已发布音乐列表。"""
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
        assert data["total"] == 2
        assert len(data["items"]) == 2
        titles = {item["music"]["title"] for item in data["items"]}
        assert "ReleaseSong1" in titles
        assert "ReleaseSong2" in titles

    async def test_list_releases_empty(self, client: TestClient, db_session: AsyncSession):
        """测试无发布记录时返回空列表。"""
        user = await _create_user(db_session, "list_release_empty")

        resp = client.get(
            f"{BASE_URL}/releases",
            headers=_auth_header(user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
