"""音乐模块测试 —— 严格遵循 TDD：先写测试，再写实现。"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import (
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    Style,
)
from echomemory_backend.models.enums import UserRole
from echomemory_backend.models.music import Music
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


def _create_user(
    db: Session,
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
    db.commit()
    db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


import uuid

def _create_style(db: Session, name: str) -> Style:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    style = Style(name=unique_name)
    db.add(style)
    db.commit()
    db.refresh(style)
    return style


def _create_language(db: Session, name: str) -> Language:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    lang = Language(name=unique_name)
    db.add(lang)
    db.commit()
    db.refresh(lang)
    return lang


def _create_instrument(db: Session, name: str) -> Instrument:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    inst = Instrument(name=unique_name)
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


def _create_emotion_tag(db: Session, name: str) -> EmotionTag:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    tag = EmotionTag(name=unique_name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _create_interest_tag(db: Session, name: str) -> InterestTag:
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"
    tag = InterestTag(name=unique_name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _create_music_directly(
    db: Session,
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
    db.commit()
    db.refresh(music)
    return music


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_oss_uploads(monkeypatch):
    """所有音乐测试自动 mock OSS 上传函数，避免依赖真实 OSS 配置。"""

    def fake_audio_upload(*args, **kwargs):
        return "https://fake-oss.example.com/musics/test.mp3"

    def fake_image_upload(*args, **kwargs):
        return "https://fake-oss.example.com/covers/test.jpg"

    def fake_lyrics_upload(*args, **kwargs):
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
    def test_import_success(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_import", role=UserRole.ADMIN.value)
        author = _create_user(db_session, "author1")
        style = _create_style(db_session, "Rock")
        lang = _create_language(db_session, "English")
        inst = _create_instrument(db_session, "Guitar")
        etag = _create_emotion_tag(db_session, "Happy")
        itag = _create_interest_tag(db_session, "Workout")

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

    def test_import_with_optional_files(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_opt", role=UserRole.ADMIN.value)
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

    def test_normal_user_cannot_import(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_import")
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

    def test_import_invalid_audio_type(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_bad_audio", role=UserRole.ADMIN.value)
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

    def test_import_missing_cover_icon(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_no_cover", role=UserRole.ADMIN.value)
        resp = client.post(
            ADMIN_IMPORT_URL,
            headers=_auth_header(admin),
            data={"title": "NoCover"},
            files={
                "audio_file": ("song.mp3", io.BytesIO(_make_audio_bytes()), "audio/mpeg"),
            },
        )
        assert resp.status_code == 422

    def test_import_invalid_release_date(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_bad_date", role=UserRole.ADMIN.value)
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


# ---------------------------------------------------------------------------
# 管理员更新 / 上架 / 下架测试
# ---------------------------------------------------------------------------

class TestAdminUpdateMusic:
    def test_update_music_info(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_update_m", role=UserRole.ADMIN.value)
        music = _create_music_directly(db_session, title="OldTitle")
        new_style = _create_style(db_session, "Jazz")

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

    def test_normal_user_cannot_update(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_update_m")
        music = _create_music_directly(db_session)
        resp = client.patch(
            f"{BASE_URL}/admin/{music.id}",
            headers=_auth_header(user),
            json={"title": "Hacked"},
        )
        assert resp.status_code == 403

    def test_update_nonexistent_music(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_nx_m", role=UserRole.ADMIN.value)
        resp = client.patch(
            f"{BASE_URL}/admin/99999",
            headers=_auth_header(admin),
            json={"title": "Ghost"},
        )
        assert resp.status_code == 404


class TestAdminPublishUnpublish:
    def test_publish_music(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_pub", role=UserRole.ADMIN.value)
        music = _create_music_directly(db_session, is_published=False)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/publish",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is True

    def test_unpublish_music(self, client: TestClient, db_session: Session):
        admin = _create_user(db_session, "admin_unpub", role=UserRole.ADMIN.value)
        music = _create_music_directly(db_session, is_published=True)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/unpublish",
            headers=_auth_header(admin),
        )
        assert resp.status_code == 200
        assert resp.json()["is_published"] is False

    def test_normal_user_cannot_publish(self, client: TestClient, db_session: Session):
        user = _create_user(db_session, "normal_pub")
        music = _create_music_directly(db_session, is_published=False)
        resp = client.post(
            f"{BASE_URL}/admin/{music.id}/publish",
            headers=_auth_header(user),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 公开查询测试
# ---------------------------------------------------------------------------

class TestGetMusic:
    def test_get_published_music(self, client: TestClient, db_session: Session):
        music = _create_music_directly(db_session, title="PublishedSong")
        resp = client.get(f"{BASE_URL}/{music.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "PublishedSong"

    def test_get_unpublished_music_returns_404(self, client: TestClient, db_session: Session):
        music = _create_music_directly(db_session, title="HiddenSong", is_published=False)
        resp = client.get(f"{BASE_URL}/{music.id}")
        assert resp.status_code == 404

    def test_get_nonexistent_music(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/99999")
        assert resp.status_code == 404


class TestListMusics:
    def test_list_published_only(self, client: TestClient, db_session: Session):
        _create_music_directly(db_session, title="Pub1", is_published=True)
        _create_music_directly(db_session, title="Pub2", is_published=True)
        _create_music_directly(db_session, title="Hidden", is_published=False)
        resp = client.get(f"{BASE_URL}/")
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data}
        assert "Pub1" in titles
        assert "Pub2" in titles
        assert "Hidden" not in titles

    def test_list_filter_by_style(self, client: TestClient, db_session: Session):
        style = _create_style(db_session, "Pop")
        _create_music_directly(db_session, title="PopSong", style_id=style.id)
        _create_music_directly(db_session, title="OtherSong")
        resp = client.get(f"{BASE_URL}/", params={"style_id": style.id})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "PopSong"

    def test_list_filter_by_vip(self, client: TestClient, db_session: Session):
        _create_music_directly(db_session, title="VipSong", is_vip=True)
        _create_music_directly(db_session, title="FreeSong", is_vip=False)
        resp = client.get(f"{BASE_URL}/", params={"is_vip": True})
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data}
        assert "VipSong" in titles
        assert "FreeSong" not in titles

    def test_list_pagination(self, client: TestClient, db_session: Session):
        for i in range(5):
            _create_music_directly(db_session, title=f"Song{i}")
        resp = client.get(f"{BASE_URL}/", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestSearchMusics:
    def test_search_by_title(self, client: TestClient, db_session: Session):
        _create_music_directly(db_session, title="Amazing Grace")
        _create_music_directly(db_session, title="Boring Tune")
        resp = client.get(f"{BASE_URL}/search", params={"q": "Amazing"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Amazing Grace"

    def test_search_no_match(self, client: TestClient):
        resp = client.get(f"{BASE_URL}/search", params={"q": "zzzzzzzzz"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_empty_query_returns_all(self, client: TestClient, db_session: Session):
        _create_music_directly(db_session, title="SongA")
        _create_music_directly(db_session, title="SongB")
        resp = client.get(f"{BASE_URL}/search")
        assert resp.status_code == 200
        data = resp.json()
        titles = {m["title"] for m in data}
        assert "SongA" in titles
        assert "SongB" in titles
