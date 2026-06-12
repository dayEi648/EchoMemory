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
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User
from echomemory_backend.services.playlist_service import DEFAULT_LIKE_PLAYLIST_TITLE

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
    is_like: bool = False,
    *,
    empty: bool = True,
) -> Playlist:
    """创建测试歌单。默认不添加歌曲（保持向后兼容）。

    Args:
        empty: 设为 False 则自动创建一首歌曲加入歌单（用于搜索等需要非空歌单的测试）。
    """
    playlist = Playlist(
        title=title,
        user_id=user_id,
        is_private=is_private,
        cover_icon_url=cover_icon_url,
        is_like=is_like,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)

    if not empty:
        music = Music(
            title=f"{title}_Song",
            is_published=True,
            file_url="https://oss.example.com/musics/test.mp3",
            cover_icon_url="https://oss.example.com/covers/icon.jpg",
        )
        db.add(music)
        await db.commit()
        await db.refresh(music)
        db.add(PlaylistMusic(playlist_id=playlist.id, music_id=music.id, ordinal=0))
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
    """测试创建歌单相关接口。"""

    async def test_create_playlist_success(self, client: TestClient, db_session: AsyncSession):
        """测试正常创建歌单，包含封面与基本信息。"""
        user = await _create_user(db_session, "create_pl_user")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            data={
                "title": "MyPlaylist",
                "description": "A test playlist",
                "is_private": "false",
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
        assert data["emotion_tags"] == []
        assert data["interest_tags"] == []
        assert data["user"]["id"] == user.id

    async def test_create_playlist_without_cover(self, client: TestClient, db_session: AsyncSession):
        """测试不上传封面时仍可成功创建歌单。"""
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
        """测试缺少必填标题时返回 422 校验错误。"""
        user = await _create_user(db_session, "create_pl_notitle")

        resp = client.post(
            BASE_URL + "/",
            headers=_auth_header(user),
            data={"description": "No title"},
        )
        assert resp.status_code == 422

    async def test_create_playlist_unauthorized(self, client: TestClient):
        """测试未登录用户创建歌单时返回 401。"""
        resp = client.post(
            BASE_URL + "/",
            data={"title": "HackPlaylist"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 查询歌单列表测试
# ---------------------------------------------------------------------------

class TestListPlaylists:
    """测试查询歌单列表相关接口。"""

    async def test_list_my_playlists(self, client: TestClient, db_session: AsyncSession):
        """测试仅返回当前用户自己的歌单，不包含他人歌单。"""
        user_a = await _create_user(db_session, "list_pl_a")
        user_b = await _create_user(db_session, "list_pl_b")

        await _create_playlist_directly(db_session, user_a.id, title="PlaylistA1")
        await _create_playlist_directly(db_session, user_a.id, title="PlaylistA2")
        await _create_playlist_directly(db_session, user_b.id, title="PlaylistB1")

        resp = client.get(BASE_URL + "/", headers=_auth_header(user_a))
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        titles = {p["title"] for p in items}
        assert "PlaylistA1" in titles
        assert "PlaylistA2" in titles
        assert "PlaylistB1" not in titles

    async def test_list_playlists_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试歌单列表的分页参数（limit/offset）生效。"""
        user = await _create_user(db_session, "list_pl_page")
        for i in range(5):
            await _create_playlist_directly(db_session, user.id, title=f"Playlist{i}")

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

        resp = client.get(
            BASE_URL + "/",
            headers=_auth_header(user),
            params={"limit": 2, "offset": 4},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["total"] == 5


# ---------------------------------------------------------------------------
# 查询歌单详情测试
# ---------------------------------------------------------------------------

class TestGetPlaylist:
    """测试查询歌单详情相关接口。"""

    async def test_get_own_playlist_detail(self, client: TestClient, db_session: AsyncSession):
        """测试获取自己创建的歌单详情，包含歌曲列表。"""
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
        """测试其他用户可正常访问公开歌单详情。"""
        owner = await _create_user(db_session, "get_pub_owner")
        viewer = await _create_user(db_session, "get_pub_viewer")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="PublicPlaylist", is_private=False
        )

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(viewer))
        assert resp.status_code == 200
        assert resp.json()["title"] == "PublicPlaylist"
        assert resp.json()["is_collected_by_me"] is False

    async def test_get_playlist_collection_status_collected(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试已收藏用户获取歌单详情时 is_collected_by_me 为 true。"""
        owner = await _create_user(db_session, "pl_col_owner")
        viewer = await _create_user(db_session, "pl_col_viewer")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="CollectedPlaylist", is_private=False
        )
        client.post(
            f"/api/v1/collections/playlists/{playlist.id}",
            headers=_auth_header(viewer),
        )
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(viewer))
        assert resp.status_code == 200
        assert resp.json()["is_collected_by_me"] is True

    async def test_get_private_playlist_of_others(self, client: TestClient, db_session: AsyncSession):
        """测试非所有者访问他人私有歌单时返回 403。"""
        owner = await _create_user(db_session, "get_priv_owner")
        viewer = await _create_user(db_session, "get_priv_viewer")
        playlist = await _create_playlist_directly(
            db_session, owner.id, title="PrivatePlaylist", is_private=True
        )

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(viewer))
        assert resp.status_code == 403

    async def test_get_nonexistent_playlist(self, client: TestClient, db_session: AsyncSession):
        """测试访问不存在的歌单时返回 404。"""
        user = await _create_user(db_session, "get_nx")
        resp = client.get(f"{BASE_URL}/99999", headers=_auth_header(user))
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 修改歌单测试
# ---------------------------------------------------------------------------

class TestUpdatePlaylist:
    """测试修改歌单相关接口。"""

    async def test_update_playlist_success(self, client: TestClient, db_session: AsyncSession):
        """测试歌单所有者成功更新歌单标题、描述及私有状态。"""
        user = await _create_user(db_session, "update_own")
        playlist = await _create_playlist_directly(
            db_session, user.id, title="OldTitle", is_private=False
        )

        resp = client.patch(
            f"{BASE_URL}/{playlist.id}",
            headers=_auth_header(user),
            json={
                "title": "NewTitle",
                "description": "Updated desc",
                "is_private": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "NewTitle"
        assert data["description"] == "Updated desc"
        assert data["is_private"] is True

    async def test_update_others_playlist(self, client: TestClient, db_session: AsyncSession):
        """测试非所有者尝试修改他人歌单时返回 403。"""
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
    """测试删除歌单相关接口。"""

    async def test_delete_playlist_success(self, client: TestClient, db_session: AsyncSession):
        """测试歌单所有者成功删除歌单，删除后无法再次访问。"""
        user = await _create_user(db_session, "delete_own")
        playlist = await _create_playlist_directly(db_session, user.id, title="ToDelete")

        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 404

    async def test_delete_others_playlist(self, client: TestClient, db_session: AsyncSession):
        """测试非所有者尝试删除他人歌单时返回 403。"""
        owner = await _create_user(db_session, "delete_other_owner")
        hacker = await _create_user(db_session, "delete_other_hacker")
        playlist = await _create_playlist_directly(db_session, owner.id, title="Protected")

        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(hacker))
        assert resp.status_code == 403

    async def test_delete_like_playlist_forbidden(self, client: TestClient, db_session: AsyncSession):
        """测试系统默认「我喜欢的音乐」歌单不可删除。"""
        user = await _create_user(db_session, "delete_like_user")
        playlist = await _create_playlist_directly(
            db_session,
            user.id,
            title=DEFAULT_LIKE_PLAYLIST_TITLE,
            is_private=True,
            is_like=True,
        )

        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 403

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 添加/移除歌曲测试
# ---------------------------------------------------------------------------

class TestAddRemoveMusic:
    """测试向歌单添加/移除歌曲相关接口。"""

    async def test_add_music_success(self, client: TestClient, db_session: AsyncSession):
        """测试成功向歌单添加歌曲，并同步更新 collect_count。"""
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

        # 验证 collect_count 同步
        await db_session.refresh(music)
        assert music.collect_count == 1

    async def test_add_unpublished_music(self, client: TestClient, db_session: AsyncSession):
        """测试向歌单添加未发布的音乐时返回 404。"""
        user = await _create_user(db_session, "add_unpub_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="AddUnpubPL")
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)

        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404

    async def test_add_duplicate_music(self, client: TestClient, db_session: AsyncSession):
        """测试向歌单重复添加同一首歌曲时返回 409。"""
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
        """测试非所有者向他人歌单添加歌曲时返回 403。"""
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
        """测试成功从歌单移除歌曲，歌单中不再包含该歌曲。"""
        user = await _create_user(db_session, "remove_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="RemovePL")
        music = await _create_music_directly(db_session, title="SongToRemove")
        await _add_music_to_playlist_directly(db_session, playlist.id, music.id)

        # 直接添加不触发 service 计数维护，手动同步初始值
        music.collect_count = 1
        await db_session.commit()

        resp = client.delete(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json()["musics"] == []

        # 验证 collect_count 不变（只增不减）
        await db_session.refresh(music)
        assert music.collect_count == 1

    async def test_remove_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        """测试从歌单移除不存在的歌曲时返回 404。"""
        user = await _create_user(db_session, "remove_nx_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="RemoveNxPL")

        resp = client.delete(
            f"{BASE_URL}/{playlist.id}/musics/99999",
            headers=_auth_header(user),
        )
        assert resp.status_code == 404


# ============================================================================
# 标签同步测试
# ============================================================================

class TestPlaylistTagSync:
    """测试歌单标签随歌曲增删自动同步。"""

    async def test_add_music_syncs_tags_to_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        """将带标签的歌曲加入歌单，歌单应自动获得该歌曲的标签。"""
        user = await _create_user(db_session, "pl_tag_sync")
        playlist = await _create_playlist_directly(db_session, user.id, title="TagSyncPL")
        music = await _create_music_directly(db_session, title="TaggedSongPL")

        # 给音乐添加标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music.id, interest_tag_id=interest_tag.id))
        await db_session.commit()

        # 通过 API 将歌曲加入歌单
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        # 验证歌单详情中包含该歌曲的标签
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        emotion_tag_ids = {t["id"] for t in data["emotion_tags"]}
        interest_tag_ids = {t["id"] for t in data["interest_tags"]}
        assert emotion_tag.id in emotion_tag_ids
        assert interest_tag.id in interest_tag_ids

    async def test_remove_music_syncs_tags_on_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        """从歌单移除歌曲后，歌单标签应清空。"""
        user = await _create_user(db_session, "pl_tag_remove")
        playlist = await _create_playlist_directly(db_session, user.id, title="TagRemovePL")
        music = await _create_music_directly(db_session, title="TaggedSongPLRemove")

        # 给音乐添加标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music.id, interest_tag_id=interest_tag.id))
        await db_session.commit()

        # 通过 API 加入歌单（触发标签同步）
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        # 确认歌单已有标签
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.json()["emotion_tags"] != []

        # 通过 API 移除歌曲
        resp = client.delete(
            f"{BASE_URL}/{playlist.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        # 验证歌单标签已清空
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["emotion_tags"] == []
        assert data["interest_tags"] == []

    async def test_add_multiple_musics_dedup_tags(
        self, client: TestClient, db_session: AsyncSession
    ):
        """向歌单添加多首标签重叠的歌曲，歌单标签应去重。"""
        user = await _create_user(db_session, "pl_dedup_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="DedupPL")
        music1 = await _create_music_directly(db_session, title="PLSong1")
        music2 = await _create_music_directly(db_session, title="PLSong2")

        # 两首歌共享同一个情感标签
        emotion_tag = await _get_first_emotion_tag(db_session)
        interest_tag1 = await _get_first_interest_tag(db_session)
        db_session.add(MusicEmotionTag(music_id=music1.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicEmotionTag(music_id=music2.id, emotion_tag_id=emotion_tag.id))
        db_session.add(MusicInterestTag(music_id=music1.id, interest_tag_id=interest_tag1.id))
        await db_session.commit()

        # 加入第一首歌
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music1.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        # 加入第二首歌
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music2.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        # 验证情感标签只出现一次（去重）
        resp = client.get(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["emotion_tags"]) == 1
        assert data["emotion_tags"][0]["id"] == emotion_tag.id
        assert len(data["interest_tags"]) == 1


# ============================================================================
# collect_count 维护验证
# ============================================================================


class TestCollectCountOnAddRemove:
    """测试 collect_count 在歌单增删操作中的维护行为。"""

    async def test_delete_playlist_syncs_collect_count(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试删除歌单后，歌曲的 collect_count 保持只增不减。"""
        user = await _create_user(db_session, "del_pl_count_user")
        playlist = await _create_playlist_directly(db_session, user.id, title="DelCountPL")
        music1 = await _create_music_directly(db_session, title="Song1")
        music2 = await _create_music_directly(db_session, title="Song2")

        # 通过 API 添加两首音乐（触发计数维护）
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music1.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        resp = client.post(
            f"{BASE_URL}/{playlist.id}/musics/{music2.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        await db_session.refresh(music1)
        await db_session.refresh(music2)
        assert music1.collect_count == 1
        assert music2.collect_count == 1

        # 删除歌单
        resp = client.delete(f"{BASE_URL}/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 204

        await db_session.refresh(music1)
        await db_session.refresh(music2)
        # collect_count 只增不减，删除歌单后不递减
        assert music1.collect_count == 1
        assert music2.collect_count == 1

    async def test_collect_count_multiple_playlists(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试同一首歌曲被加入多个歌单时 collect_count 正确累加，移除后不递减。"""
        user = await _create_user(db_session, "multi_pl_user")
        playlist1 = await _create_playlist_directly(db_session, user.id, title="MultiPL1")
        playlist2 = await _create_playlist_directly(db_session, user.id, title="MultiPL2")
        music = await _create_music_directly(db_session, title="SharedSong")

        # 同一首音乐加入两个歌单
        resp = client.post(
            f"{BASE_URL}/{playlist1.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201
        resp = client.post(
            f"{BASE_URL}/{playlist2.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 201

        await db_session.refresh(music)
        assert music.collect_count == 2

        # 从其中一个歌单移除
        resp = client.delete(
            f"{BASE_URL}/{playlist1.id}/musics/{music.id}",
            headers=_auth_header(user),
        )
        assert resp.status_code == 204

        await db_session.refresh(music)
        # collect_count 只增不减，从歌单移除后不递减
        assert music.collect_count == 2


class TestSearchPlaylists:
    """测试公开歌单搜索接口。"""

    async def test_search_by_title(self, client: TestClient, db_session: AsyncSession):
        """测试按标题关键词搜索公开歌单。"""
        owner = await _create_user(db_session, "search_pl_owner")
        await _create_playlist_directly(
            db_session, owner.id, title="Summer Vibes", is_private=False, empty=False,
        )
        await _create_playlist_directly(
            db_session, owner.id, title="Winter Chill", is_private=False, empty=False,
        )

        resp = client.get(f"{BASE_URL}/search", params={"q": "Summer"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Summer Vibes"

    async def test_search_excludes_private_playlists(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试搜索结果不包含私密歌单。"""
        owner = await _create_user(db_session, "search_private_owner")
        await _create_playlist_directly(
            db_session, owner.id, title="Hidden Mix", is_private=True, empty=False,
        )
        await _create_playlist_directly(
            db_session, owner.id, title="Hidden Public", is_private=False, empty=False,
        )

        resp = client.get(f"{BASE_URL}/search", params={"q": "Hidden"})
        assert resp.status_code == 200
        data = resp.json()
        titles = {item["title"] for item in data["items"]}
        assert "Hidden Public" in titles
        assert "Hidden Mix" not in titles


class TestListPublicPlaylists:
    """测试用户公开歌单列表接口。"""

    async def test_list_public_playlists(self, client: TestClient, db_session: AsyncSession):
        """测试返回指定用户的公开歌单。"""
        owner = await _create_user(db_session, "public_pl_owner")
        await _create_playlist_directly(
            db_session, owner.id, title="Public One", is_private=False
        )
        await _create_playlist_directly(
            db_session, owner.id, title="Private One", is_private=True
        )

        resp = client.get(f"{BASE_URL}/public", params={"user_id": owner.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Public One"

    async def test_list_public_playlists_empty_for_no_public(
        self, client: TestClient, db_session: AsyncSession
    ):
        """测试用户仅有私密歌单时返回空列表。"""
        owner = await _create_user(db_session, "only_private_owner")
        await _create_playlist_directly(
            db_session, owner.id, title="Secret List", is_private=True
        )

        resp = client.get(f"{BASE_URL}/public", params={"user_id": owner.id})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []
