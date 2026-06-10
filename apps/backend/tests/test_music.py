"""音乐模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.dictionary import (
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    Style,
)
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.models.user import User

BASE_URL = "/api/v1/music"
ADMIN_IMPORT_URL = f"{BASE_URL}/admin/import"


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def _make_audio_bytes() -> bytes:
    """生成假的音频文件字节（仅用于测试文件上传流程）。"""
    return b"FAKE_AUDIO_DATA" * 100


def _make_lyrics_bytes() -> bytes:
    return b"[00:00.00]Test lyrics\n[00:05.00]Line two"


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


import uuid

async def _create_style(db: AsyncSession, name: str) -> Style:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    style = Style(name=unique_name)
    db.add(style)
    await db.commit()
    await db.refresh(style)
    return style


async def _create_language(db: AsyncSession, name: str) -> Language:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    lang = Language(name=unique_name)
    db.add(lang)
    await db.commit()
    await db.refresh(lang)
    return lang


async def _create_instrument(db: AsyncSession, name: str) -> Instrument:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    inst = Instrument(name=unique_name)
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


async def _create_emotion_tag(db: AsyncSession, name: str) -> EmotionTag:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    tag = EmotionTag(name=unique_name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def _create_interest_tag(db: AsyncSession, name: str) -> InterestTag:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    tag = InterestTag(name=unique_name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def _create_music_directly(
    db: AsyncSession,
    title: str = "TestSong",
    is_published: bool = True,
    is_vip: bool = False,
    style_id: int | None = None,
) -> Music:
    music = Music(
        title=title,
        is_published=is_published,
        is_vip=is_vip,
        style_id=style_id,
        file_url="https://oss.example.com/musics/test.mp3",
        cover_icon_url="https://oss.example.com/covers/icon.jpg",
    )
    db.add(music)
    await db.commit()
    await db.refresh(music)
    return music


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_oss_uploads(monkeypatch):
    """所有音乐测试自动 mock OSS 上传函数，避免依赖真实 OSS 配置。"""

    async def fake_audio_upload(*args, **kwargs):
        return "https://fake-oss.example.com/musics/test.mp3"

    async def fake_image_upload(*args, **kwargs):
        return "https://fake-oss.example.com/covers/test.jpg"

    async def fake_lyrics_upload(*args, **kwargs):
        return "https://fake-oss.example.com/lyrics/test.lrc"

    monkeypatch.setattr(
        "echomemory_backend.core.oss_client.upload_audio_to_oss",
        fake_audio_upload,
    )
    monkeypatch.setattr(
        "echomemory_backend.core.oss_client.upload_image_to_oss",
        fake_image_upload,
    )
    monkeypatch.setattr(
        "echomemory_backend.core.oss_client.upload_lyrics_to_oss",
        fake_lyrics_upload,
    )


# ---------------------------------------------------------------------------
# 管理员导入测试
# ---------------------------------------------------------------------------

class TestAdminImportMusic:
    """测试管理员导入音乐功能。"""

    async def test_import_success(self, client: TestClient, db_session: AsyncSession):
        """测试管理员成功导入一首完整的音乐。"""
        admin = await _create_user(db_session, "admin_import", role=UserRole.ADMIN.value)
        author = await _create_user(db_session, "author1")
        style = await _create_style(db_session, "Rock")
        lang = await _create_language(db_session, "English")
        inst = await _create_instrument(db_session, "Guitar")
        etag = await _create_emotion_tag(db_session, "Happy")
        itag = await _create_interest_tag(db_session, "Workout")

        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={
                "title": "MySong",
                "style_id": style.id,
                "language_id": lang.id,
                "author_ids": author.id,
                "instrument_ids": inst.id,
                "emotion_tag_ids": etag.id,
                "interest_tag_ids": itag.id,
                "release_date": "2024-01-15",
                "source": "TestSource",
            },
            files={
                "audio_file": ("song.mp3", io.BytesIO(_make_audio_bytes()), "audio/mpeg"),
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "MySong"
        assert data["is_published"] is False
        assert data["style"]["name"] == style.name
        assert data["language"]["name"] == lang.name
        assert len(data["authors"]) == 1
        assert data["authors"][0]["username"] == "author1"
        assert len(data["instruments"]) == 1
        assert len(data["emotion_tags"]) == 1
        assert len(data["interest_tags"]) == 1
        assert data["file_url"] == "https://fake-oss.example.com/musics/test.mp3"
        assert data["cover_icon_url"] == "https://fake-oss.example.com/covers/test.jpg"
        assert data["source"] == "TestSource"

    async def test_import_with_optional_files(self, client: TestClient, db_session: AsyncSession):
        """测试导入音乐时上传可选文件（歌词、多种封面）。"""
        admin = await _create_user(db_session, "admin_opt", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "FullSong"},
            files={
                "audio_file": ("song.flac", io.BytesIO(_make_audio_bytes()), "audio/flac"),
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover_home": ("home.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "cover_play": ("play.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
                "lyrics_file": ("song.lrc", io.BytesIO(_make_lyrics_bytes()), "text/plain"),
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["lyrics_url"] == "https://fake-oss.example.com/lyrics/test.lrc"
        assert data["cover_home_url"] == "https://fake-oss.example.com/covers/test.jpg"
        assert data["cover_play_url"] == "https://fake-oss.example.com/covers/test.jpg"

    async def test_normal_user_cannot_import(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限调用管理员导入接口。"""
        user = await _create_user(db_session, "normal_import")
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(user),
            data={"title": "HackSong"},
            files={
                "audio_file": ("song.mp3", io.BytesIO(_make_audio_bytes()), "audio/mpeg"),
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 403

    async def test_import_invalid_audio_type(self, client: TestClient, db_session: AsyncSession):
        """测试上传非法音频格式时返回 422。"""
        admin = await _create_user(db_session, "admin_bad_audio", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "BadSong"},
            files={
                "audio_file": ("song.exe", b"not audio", "application/octet-stream"),
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 422

    async def test_import_missing_cover_icon(self, client: TestClient, db_session: AsyncSession):
        """测试缺少必填的封面图标时返回 422。"""
        admin = await _create_user(db_session, "admin_no_cover", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "NoCover"},
            files={
                "audio_file": ("song.mp3", io.BytesIO(_make_audio_bytes()), "audio/mpeg"),
            },
        )
        assert resp.status_code == 422

    async def test_import_invalid_release_date(self, client: TestClient, db_session: AsyncSession):
        """测试传入非法发布日期格式时返回 422。"""
        admin = await _create_user(db_session, "admin_bad_date", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "BadDate", "release_date": "not-a-date"},
            files={
                "audio_file": ("song.mp3", io.BytesIO(_make_audio_bytes()), "audio/mpeg"),
                "cover_icon": ("icon.jpg", io.BytesIO(_make_image_bytes()), "image/jpeg"),
            },
        )
        assert resp.status_code == 422

    async def test_import_cleans_uploaded_files_when_optional_upload_fails(
        self,
        client: TestClient,
        db_session: AsyncSession,
        monkeypatch,
    ):
        """测试可选文件上传失败时清理此前已上传的 OSS 文件。"""
        deleted_urls: list[str] = []

        async def fake_audio_upload(*args, **kwargs):
            return "https://fake-oss.example.com/musics/cleanup.mp3"

        async def fake_cover_upload(*args, **kwargs):
            return "https://fake-oss.example.com/covers/cleanup.jpg"

        async def fake_optional_upload(*args, **kwargs):
            raise HTTPException(status_code=422, detail="optional image failed")

        async def fake_delete(url: str):
            deleted_urls.append(url)

        monkeypatch.setattr(
            "echomemory_backend.core.oss_client.upload_audio_to_oss",
            fake_audio_upload,
        )
        monkeypatch.setattr(
            "echomemory_backend.core.oss_client.upload_image_to_oss",
            fake_cover_upload,
        )
        monkeypatch.setattr(
            "echomemory_backend.api.v1.endpoints.music.upload_optional_image",
            fake_optional_upload,
        )
        monkeypatch.setattr(
            "echomemory_backend.core.oss_client.delete_object_by_url",
            fake_delete,
        )

        admin = await _create_user(
            db_session,
            "admin_cleanup_optional",
            role=UserRole.ADMIN.value,
        )
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "CleanupSong"},
            files={
                "audio_file": (
                    "song.mp3",
                    io.BytesIO(_make_audio_bytes()),
                    "audio/mpeg",
                ),
                "cover_icon": (
                    "icon.jpg",
                    io.BytesIO(_make_image_bytes()),
                    "image/jpeg",
                ),
                "cover_home": (
                    "home.jpg",
                    io.BytesIO(_make_image_bytes()),
                    "image/jpeg",
                ),
            },
        )

        assert resp.status_code == 422
        assert deleted_urls == [
            "https://fake-oss.example.com/musics/cleanup.mp3",
            "https://fake-oss.example.com/covers/cleanup.jpg",
        ]


# ---------------------------------------------------------------------------
# 管理员更新 / 上架 / 下架测试
# ---------------------------------------------------------------------------

class TestAdminUpdateMusic:
    """测试管理员更新音乐信息功能。"""

    async def test_update_music_info(self, client: TestClient, db_session: AsyncSession):
        """测试管理员成功更新音乐的标题、VIP 状态和风格。"""
        admin = await _create_user(db_session, "admin_update_m", role=UserRole.ADMIN.value)
        music = await _create_music_directly(db_session, title="OldTitle")
        new_style = await _create_style(db_session, "Jazz")

        resp = client.patch(
            f"{BASE_URL}/admin/{music.id}",
            headers=_auth_header(admin),
            json={
                "title": "NewTitle",
                "is_vip": True,
                "style_id": new_style.id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "NewTitle"
        assert data["is_vip"] is True
        assert data["style"]["name"] == new_style.name

    async def test_normal_user_cannot_update(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限调用管理员更新接口。"""
        user = await _create_user(db_session, "normal_update_m")
        music = await _create_music_directly(db_session)
        resp = client.patch(
            f"{BASE_URL}/admin/{music.id}",
            headers=_auth_header(user),
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403

    async def test_update_nonexistent_music(self, client: TestClient, db_session: AsyncSession):
        """测试管理员更新不存在的音乐时返回 404。"""
        admin = await _create_user(db_session, "admin_nx_m", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{BASE_URL}/admin/999",
            headers=_auth_header(admin),
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404


class TestAdminPublishUnpublish:
    """测试管理员上架与下架音乐功能。"""

    async def test_publish_music(self, client: TestClient, db_session: AsyncSession):
        """测试管理员将未上架音乐变为上架状态。"""
        admin = await _create_user(db_session, "admin_pub", role=UserRole.ADMIN.value)
        music = await _create_music_directly(db_session, is_published=False)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/publish",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is True

    async def test_unpublish_music(self, client: TestClient, db_session: AsyncSession):
        """测试管理员将已上架音乐变为下架状态。"""
        admin = await _create_user(db_session, "admin_unpub", role=UserRole.ADMIN.value)
        music = await _create_music_directly(db_session, is_published=True)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/unpublish",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False

    async def test_normal_user_cannot_publish(self, client: TestClient, db_session: AsyncSession):
        """测试普通用户无权限调用管理员上架接口。"""
        user = await _create_user(db_session, "normal_pub")
        music = await _create_music_directly(db_session, is_published=False)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/publish",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 公开查询测试
# ---------------------------------------------------------------------------

class TestGetMusic:
    """测试公开查询单首音乐详情功能。"""

    async def test_get_published_music(self, client: TestClient, db_session: AsyncSession):
        """测试正常获取已上架的音乐详情。"""
        music = await _create_music_directly(db_session, title="PublishedSong")
        resp = client.get(f"{BASE_URL}/{music.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "PublishedSong"

    async def test_get_unpublished_music_returns_404(self, client: TestClient, db_session: AsyncSession):
        """测试获取未上架音乐时返回 404。"""
        music = await _create_music_directly(db_session, title="HiddenSong", is_published=False)
        resp = client.get(f"{BASE_URL}/{music.id}")
        assert resp.status_code == 404

    async def test_get_nonexistent_music(self, client: TestClient):
        """测试获取不存在的音乐时返回 404。"""
        resp = client.get(f"{BASE_URL}/999")
        assert resp.status_code == 404


class TestListMusics:
    """测试公开查询音乐列表功能。"""

    async def test_list_published_only(self, client: TestClient, db_session: AsyncSession):
        """测试列表仅返回已上架的音乐。"""
        await _create_music_directly(db_session, title="Pub1", is_published=True)
        await _create_music_directly(db_session, title="Pub2", is_published=True)
        await _create_music_directly(db_session, title="Hidden", is_published=False)
        resp = client.get(f"{BASE_URL}/")
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data}
        assert "Pub1" in titles
        assert "Pub2" in titles
        assert "Hidden" not in titles

    async def test_list_filter_by_style(self, client: TestClient, db_session: AsyncSession):
        """测试按风格 ID 筛选音乐列表。"""
        style = await _create_style(db_session, "Pop")
        await _create_music_directly(db_session, title="PopSong", style_id=style.id)
        await _create_music_directly(db_session, title="OtherSong")
        resp = client.get(f"{BASE_URL}/", params={"style_id": style.id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "PopSong"

    async def test_list_filter_by_vip(self, client: TestClient, db_session: AsyncSession):
        """测试按 VIP 状态筛选音乐列表。"""
        await _create_music_directly(db_session, title="VipSong", is_vip=True)
        await _create_music_directly(db_session, title="FreeSong", is_vip=False)
        resp = client.get(f"{BASE_URL}/", params={"is_vip": True})
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data}
        assert "VipSong" in titles
        assert "FreeSong" not in titles

    async def test_list_pagination(self, client: TestClient, db_session: AsyncSession):
        """测试音乐列表的分页参数生效。"""
        for i in range(5):
            await _create_music_directly(db_session, title=f"Song{i}")
        resp = client.get(f"{BASE_URL}/", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestSearchMusics:
    """测试音乐搜索功能。"""

    async def test_search_by_title(self, client: TestClient, db_session: AsyncSession):
        """测试按标题关键字搜索音乐。"""
        await _create_music_directly(db_session, title="Amazing Grace")
        await _create_music_directly(db_session, title="Boring Tune")
        resp = client.get(f"{BASE_URL}/search", params={"q": "Amazing"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Amazing Grace"
        assert data["total"] == 1

    async def test_search_no_match(self, client: TestClient):
        """测试无匹配结果时返回空列表。"""
        resp = client.get(f"{BASE_URL}/search", params={"q": "zzzzzzzzz"})
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0}

    async def test_search_empty_query_returns_all(self, client: TestClient, db_session: AsyncSession):
        """测试空查询时返回全部已上架音乐。"""
        await _create_music_directly(db_session, title="SongA")
        await _create_music_directly(db_session, title="SongB")
        resp = client.get(f"{BASE_URL}/search")
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data["items"]}
        assert "SongA" in titles
        assert "SongB" in titles
        assert data["total"] == 2


# ---------------------------------------------------------------------------
# 标签级联更新测试
# ---------------------------------------------------------------------------

class TestMusicTagCascadeUpdate:
    """测试音乐标签修改后向专辑和歌单的级联同步功能。"""

    async def test_update_music_tags_syncs_album_and_playlist(
        self, client: TestClient, db_session: AsyncSession
    ):
        """修改音乐标签后，包含该音乐的专辑和歌单标签应同步更新。"""
        admin = await _create_user(db_session, "admin_cascade", role=UserRole.ADMIN.value)
        user = await _create_user(db_session, "playlist_owner")

        # 创建音乐和容器
        music = await _create_music_directly(db_session, title="CascadeSong")
        album = Album(title="CascadeAlbum")
        db_session.add(album)
        await db_session.commit()
        await db_session.refresh(album)
        playlist = Playlist(title="CascadePlaylist", user_id=user.id)
        db_session.add(playlist)
        await db_session.commit()
        await db_session.refresh(playlist)

        # 加入专辑和歌单
        db_session.add(AlbumMusic(album_id=album.id, music_id=music.id, ordinal=0))
        db_session.add(PlaylistMusic(playlist_id=playlist.id, music_id=music.id, ordinal=0))
        await db_session.commit()

        # 给音乐添加初始标签
        old_etag = await _create_emotion_tag(db_session, "OldEmotion")
        old_itag = await _create_interest_tag(db_session, "OldInterest")
        db_session.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=old_etag.id))
        db_session.add(MusicInterestTag(music_id=music.id, interest_tag_id=old_itag.id))
        await db_session.commit()

        # 准备新标签
        new_etag = await _create_emotion_tag(db_session, "NewEmotion")
        new_itag = await _create_interest_tag(db_session, "NewInterest")

        # 通过 API 更新音乐标签
        resp = client.patch(
            f"{BASE_URL}/admin/{music.id}",
            headers=_auth_header(admin),
            json={
                "emotion_tag_ids": [new_etag.id],
                "interest_tag_ids": [new_itag.id],
            },
        )
        assert resp.status_code == 200

        # 验证专辑标签已更新
        resp = client.get(f"/api/v1/albums/{album.id}")
        assert resp.status_code == 200
        data = resp.json()
        album_etag_ids = {t["id"] for t in data["emotion_tags"]}
        album_itag_ids = {t["id"] for t in data["interest_tags"]}
        assert old_etag.id not in album_etag_ids
        assert new_etag.id in album_etag_ids
        assert old_itag.id not in album_itag_ids
        assert new_itag.id in album_itag_ids

        # 验证歌单标签已更新
        resp = client.get(f"/api/v1/playlists/{playlist.id}", headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        pl_etag_ids = {t["id"] for t in data["emotion_tags"]}
        pl_itag_ids = {t["id"] for t in data["interest_tags"]}
        assert old_etag.id not in pl_etag_ids
        assert new_etag.id in pl_etag_ids
        assert old_itag.id not in pl_itag_ids
        assert new_itag.id in pl_itag_ids
