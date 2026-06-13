from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import Language, Style
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.user import User
from echomemory_backend.models.user_tag import (
    UserEmotionTag,
    UserInterestTag,
    UserLanguage,
    UserStyle,
)
from echomemory_backend.services.user_tag_service import recalculate_user_tags

BASE = "/api/v1/users"
EMOTION_TAGS_URL = f"{BASE}/me/emotion-tags"
INTEREST_TAGS_URL = f"{BASE}/me/interest-tags"
STYLES_URL = f"{BASE}/me/styles"
LANGUAGES_URL = f"{BASE}/me/languages"
RECALCULATE_URL = f"{BASE}/me/recalculate-tags"
PLAY_HISTORY_URL = "/api/v1/play-history"


async def _create_user(db: AsyncSession, username: str, password: str = "secret") -> User:
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        nickname=username.capitalize(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_music_with_tags(
    db: AsyncSession,
    title: str = "TestSong",
    style_id: int | None = None,
    language_id: int | None = None,
    emotion_tag_ids: list[int] | None = None,
    interest_tag_ids: list[int] | None = None,
) -> Music:
    music = Music(
        title=title,
        is_published=True,
        style_id=style_id,
        language_id=language_id,
        file_url="https://oss.example.com/musics/test.mp3",
    )
    db.add(music)
    await db.commit()
    await db.refresh(music)
    for tid in emotion_tag_ids or []:
        db.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=tid))
    for tid in interest_tag_ids or []:
        db.add(MusicInterestTag(music_id=music.id, interest_tag_id=tid))
    await db.commit()
    return music


async def _create_playlist_with_tags(
    db: AsyncSession,
    user_id: int,
    title: str = "TestPlaylist",
    emotion_tag_ids: list[int] | None = None,
    interest_tag_ids: list[int] | None = None,
) -> Playlist:
    playlist = Playlist(title=title, user_id=user_id)
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    for tid in emotion_tag_ids or []:
        db.add(PlaylistEmotionTag(playlist_id=playlist.id, emotion_tag_id=tid))
    for tid in interest_tag_ids or []:
        db.add(PlaylistInterestTag(playlist_id=playlist.id, interest_tag_id=tid))
    await db.commit()
    return playlist


async def _create_play_history_directly(
    db: AsyncSession, user_id: int, music_id: int, play_count: int = 1
) -> PlayHistory:
    history = PlayHistory(user_id=user_id, music_id=music_id, play_count=play_count)
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


class TestEmotionTags:
    """测试用户情绪标签查询接口。"""

    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        """测试情绪标签列表为空时返回空数组。"""
        user = await _create_user(db_session, "empty_emotion")
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
        """测试情绪标签列表正确返回用户已有的标签。"""
        user = await _create_user(db_session, "emotion_user")
        db_session.add(UserEmotionTag(user_id=user.id, emotion_tag_id=1))
        db_session.add(UserEmotionTag(user_id=user.id, emotion_tag_id=2))
        await db_session.commit()

        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}
        names = {item["name"] for item in data}
        assert names == {"治愈", "激昂"}

    async def test_unauthorized(self, client: TestClient):
        """测试未授权访问情绪标签接口时返回 401。"""
        resp = client.get(EMOTION_TAGS_URL)
        assert resp.status_code == 401


class TestInterestTags:
    """测试用户兴趣标签查询接口。"""

    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        """测试兴趣标签列表为空时返回空数组。"""
        user = await _create_user(db_session, "empty_interest")
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
        """测试兴趣标签列表正确返回用户已有的标签。"""
        user = await _create_user(db_session, "interest_user")
        db_session.add(UserInterestTag(user_id=user.id, interest_tag_id=1))
        db_session.add(UserInterestTag(user_id=user.id, interest_tag_id=2))
        await db_session.commit()

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}
        names = {item["name"] for item in data}
        assert names == {"运动", "学习"}

    async def test_unauthorized(self, client: TestClient):
        """测试未授权访问兴趣标签接口时返回 401。"""
        resp = client.get(INTEREST_TAGS_URL)
        assert resp.status_code == 401


class TestRecalculateUserTags:
    """测试用户标签重新计算功能。"""

    async def test_empty_data(self, client: TestClient, db_session: AsyncSession):
        """无听歌历史、无歌单 → 用户标签为空。"""
        user = await _create_user(db_session, "recalc_empty")
        await recalculate_user_tags(db_session, user.id)

        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_only_play_history(self, client: TestClient, db_session: AsyncSession):
        """仅听歌历史 → 标签按历史音乐标签频率计算。"""
        user = await _create_user(db_session, "recalc_history")
        music = await _create_music_with_tags(
            db_session,
            emotion_tag_ids=[1, 2],
            interest_tag_ids=[1, 2],
        )
        await _create_play_history_directly(db_session, user.id, music.id)
        await recalculate_user_tags(db_session, user.id)

        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2}

    async def test_only_playlists(self, client: TestClient, db_session: AsyncSession):
        """仅歌单 → 标签按歌单标签频率计算。"""
        user = await _create_user(db_session, "recalc_playlist")
        await _create_playlist_with_tags(
            db_session,
            user_id=user.id,
            emotion_tag_ids=[3, 4],
            interest_tag_ids=[3, 4],
        )
        await recalculate_user_tags(db_session, user.id)

        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {3, 4}

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {3, 4}

    async def test_mixed_sources(self, client: TestClient, db_session: AsyncSession):
        """听歌历史 + 歌单 → 合并频率计算。"""
        user = await _create_user(db_session, "recalc_mixed")
        # 音乐 A：情绪[1]，兴趣[1]
        music_a = await _create_music_with_tags(
            db_session,
            title="SongA",
            emotion_tag_ids=[1],
            interest_tag_ids=[1],
        )
        # 音乐 B：情绪[1,2]，兴趣[1,2]
        music_b = await _create_music_with_tags(
            db_session,
            title="SongB",
            emotion_tag_ids=[1, 2],
            interest_tag_ids=[1, 2],
        )
        await _create_play_history_directly(db_session, user.id, music_a.id)
        await _create_play_history_directly(db_session, user.id, music_b.id)

        # 歌单：情绪[1,3]，兴趣[1,3]
        await _create_playlist_with_tags(
            db_session,
            user_id=user.id,
            emotion_tag_ids=[1, 3],
            interest_tag_ids=[1, 3],
        )

        await recalculate_user_tags(db_session, user.id)

        # 情绪合并频率：1(3), 2(1), 3(1) → 全部 <=5 保留
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2, 3}

        # 兴趣同理
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2, 3}

    async def test_tie_at_fifth_place(self, client: TestClient, db_session: AsyncSession):
        """第 5 名存在并列 → 保留超过 5 个标签。"""
        user = await _create_user(db_session, "recalc_tie")

        # 播放历史（4 首歌）
        # 歌1: [1,2] → 1,2
        m1 = await _create_music_with_tags(db_session, "M1", emotion_tag_ids=[1, 2])
        # 歌2: [1,3] → 1,3
        m2 = await _create_music_with_tags(db_session, "M2", emotion_tag_ids=[1, 3])
        # 歌3: [1,4] → 1,4
        m3 = await _create_music_with_tags(db_session, "M3", emotion_tag_ids=[1, 4])
        # 歌4: [7] → 7
        m4 = await _create_music_with_tags(db_session, "M4", emotion_tag_ids=[7])

        await _create_play_history_directly(db_session, user.id, m1.id)
        await _create_play_history_directly(db_session, user.id, m2.id)
        await _create_play_history_directly(db_session, user.id, m3.id)
        await _create_play_history_directly(db_session, user.id, m4.id)

        # 3 个歌单
        await _create_playlist_with_tags(
            db_session, user_id=user.id, emotion_tag_ids=[2, 5]
        )
        await _create_playlist_with_tags(
            db_session, user_id=user.id, emotion_tag_ids=[3, 6]
        )
        await _create_playlist_with_tags(
            db_session, user_id=user.id, emotion_tag_ids=[4, 5, 6]
        )

        await recalculate_user_tags(db_session, user.id)

        # 情绪合并频率：1(3), 2(2), 3(2), 4(2), 5(2), 6(2), 7(1)
        # threshold = 第5个频率 = 2，保留 >=2 的 → 6 个
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {1, 2, 3, 4, 5, 6}
        assert len(data) == 6

    async def test_auto_trigger_via_play_history_api(
        self, client: TestClient, db_session: AsyncSession
    ):
        """通过播放历史 API 记录播放后，用户标签应自动更新。"""
        user = await _create_user(db_session, "recalc_auto")
        music = await _create_music_with_tags(
            db_session,
            emotion_tag_ids=[8, 9],
            interest_tag_ids=[8, 9],
        )

        # 记录播放（会触发自动重算）
        resp = client.post(
            PLAY_HISTORY_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201

        # 验证情绪标签已自动更新
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {8, 9}

        # 验证兴趣标签已自动更新
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        tag_ids = {item["tag_id"] for item in data}
        assert tag_ids == {8, 9}

    async def test_play_count_weights_tags(
        self, client: TestClient, db_session: AsyncSession
    ):
        """播放次数更高的歌曲，其标签在计算时应获得更高权重。"""
        user = await _create_user(db_session, "recalc_weights")
        # 音乐 A：情绪标签 [1]，播放 1 次
        music_a = await _create_music_with_tags(
            db_session,
            title="SongA",
            emotion_tag_ids=[1],
            interest_tag_ids=[1],
        )
        # 音乐 B：情绪标签 [2]，播放 5 次
        music_b = await _create_music_with_tags(
            db_session,
            title="SongB",
            emotion_tag_ids=[2],
            interest_tag_ids=[2],
        )
        await _create_play_history_directly(db_session, user.id, music_a.id, play_count=1)
        await _create_play_history_directly(db_session, user.id, music_b.id, play_count=5)

        await recalculate_user_tags(db_session, user.id)

        # 情绪标签按 play_count 加权后：1(1), 2(5)
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["tag_id"] == 2
        assert data[1]["tag_id"] == 1

        # 兴趣标签同理
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["tag_id"] == 2
        assert data[1]["tag_id"] == 1

    async def test_manual_refresh_endpoint(
        self, client: TestClient, db_session: AsyncSession
    ):
        """手动刷新接口应正确重新计算并返回 204。"""
        user = await _create_user(db_session, "recalc_manual")
        music = await _create_music_with_tags(
            db_session,
            emotion_tag_ids=[10],
            interest_tag_ids=[10],
        )
        await _create_play_history_directly(db_session, user.id, music.id)

        # 调用手动刷新
        resp = client.post(RECALCULATE_URL, headers=_auth_header(user))
        assert resp.status_code == 204

        # 验证标签已更新
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == 10

        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == 10

    async def test_unauthorized_manual_refresh(self, client: TestClient):
        """测试未授权访问手动刷新标签接口时返回 401。"""
        resp = client.post(RECALCULATE_URL)
        assert resp.status_code == 401


class TestUserStyleAndLanguagePreferences:
    """测试用户风格与语言偏好计算。"""

    async def test_play_history_generates_style_and_language_preferences(
        self, client: TestClient, db_session: AsyncSession
    ):
        """播放历史中的音乐风格与语言应被计算为用户偏好。"""
        user = await _create_user(db_session, "pref_history")
        style = Style(name="Rock")
        language = Language(name="English")
        db_session.add(style)
        db_session.add(language)
        await db_session.commit()
        await db_session.refresh(style)
        await db_session.refresh(language)

        music = await _create_music_with_tags(
            db_session,
            title="RockSong",
            style_id=style.id,
            language_id=language.id,
        )
        await _create_play_history_directly(db_session, user.id, music.id, play_count=3)
        await recalculate_user_tags(db_session, user.id)

        styles = list(
            (
                await db_session.execute(
                    select(UserStyle).where(UserStyle.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(styles) == 1
        assert styles[0].style_id == style.id

        languages = list(
            (
                await db_session.execute(
                    select(UserLanguage).where(UserLanguage.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(languages) == 1
        assert languages[0].language_id == language.id

    async def test_playlist_generates_style_and_language_preferences(
        self, client: TestClient, db_session: AsyncSession
    ):
        """用户歌单中的音乐风格与语言应被计算为用户偏好。"""
        user = await _create_user(db_session, "pref_playlist")
        style = Style(name="Pop")
        language = Language(name="Chinese")
        db_session.add(style)
        db_session.add(language)
        await db_session.commit()
        await db_session.refresh(style)
        await db_session.refresh(language)

        music = await _create_music_with_tags(
            db_session,
            title="PopSong",
            style_id=style.id,
            language_id=language.id,
        )
        playlist = Playlist(title="MyPlaylist", user_id=user.id)
        db_session.add(playlist)
        await db_session.commit()
        await db_session.refresh(playlist)
        db_session.add(PlaylistMusic(playlist_id=playlist.id, music_id=music.id, ordinal=0))
        await db_session.commit()

        await recalculate_user_tags(db_session, user.id)

        styles = list(
            (
                await db_session.execute(
                    select(UserStyle).where(UserStyle.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(styles) == 1
        assert styles[0].style_id == style.id

        languages = list(
            (
                await db_session.execute(
                    select(UserLanguage).where(UserLanguage.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(languages) == 1
        assert languages[0].language_id == language.id

    async def test_play_count_weights_style_and_language_preferences(
        self, client: TestClient, db_session: AsyncSession
    ):
        """播放次数更高的音乐，其风格与语言应获得更高权重。"""
        user = await _create_user(db_session, "pref_weights")
        style_a = Style(name="Jazz")
        style_b = Style(name="Classical")
        language_a = Language(name="French")
        language_b = Language(name="Japanese")
        db_session.add_all([style_a, style_b, language_a, language_b])
        await db_session.commit()
        await db_session.refresh(style_a)
        await db_session.refresh(style_b)
        await db_session.refresh(language_a)
        await db_session.refresh(language_b)

        music_a = await _create_music_with_tags(
            db_session,
            title="JazzFrench",
            style_id=style_a.id,
            language_id=language_a.id,
        )
        music_b = await _create_music_with_tags(
            db_session,
            title="ClassicalJapanese",
            style_id=style_b.id,
            language_id=language_b.id,
        )
        await _create_play_history_directly(db_session, user.id, music_a.id, play_count=1)
        await _create_play_history_directly(db_session, user.id, music_b.id, play_count=5)

        await recalculate_user_tags(db_session, user.id)

        styles = list(
            (
                await db_session.execute(
                    select(UserStyle)
                    .where(UserStyle.user_id == user.id)
                    .order_by(UserStyle.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        assert len(styles) == 2
        assert styles[0].style_id == style_b.id
        assert styles[1].style_id == style_a.id

        languages = list(
            (
                await db_session.execute(
                    select(UserLanguage)
                    .where(UserLanguage.user_id == user.id)
                    .order_by(UserLanguage.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        assert len(languages) == 2
        assert languages[0].language_id == language_b.id
        assert languages[1].language_id == language_a.id


class TestUserStyleAndLanguageEndpoints:
    """测试用户风格与语言偏好查询接口。"""

    async def test_get_my_styles(self, client: TestClient, db_session: AsyncSession):
        """获取当前用户的风格偏好列表。"""
        user = await _create_user(db_session, "endpoint_styles")
        style = Style(name="Metal")
        db_session.add(style)
        await db_session.commit()
        await db_session.refresh(style)
        db_session.add(UserStyle(user_id=user.id, style_id=style.id))
        await db_session.commit()

        resp = client.get(STYLES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == style.id
        assert data[0]["name"] == "Metal"

    async def test_get_my_styles_empty(self, client: TestClient, db_session: AsyncSession):
        """风格偏好列表为空时返回空数组。"""
        user = await _create_user(db_session, "endpoint_styles_empty")
        resp = client.get(STYLES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_my_languages(self, client: TestClient, db_session: AsyncSession):
        """获取当前用户的语言偏好列表。"""
        user = await _create_user(db_session, "endpoint_languages")
        language = Language(name="Korean")
        db_session.add(language)
        await db_session.commit()
        await db_session.refresh(language)
        db_session.add(UserLanguage(user_id=user.id, language_id=language.id))
        await db_session.commit()

        resp = client.get(LANGUAGES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == language.id
        assert data[0]["name"] == "Korean"

    async def test_get_my_languages_empty(self, client: TestClient, db_session: AsyncSession):
        """语言偏好列表为空时返回空数组。"""
        user = await _create_user(db_session, "endpoint_languages_empty")
        resp = client.get(LANGUAGES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_my_styles_unauthorized(self, client: TestClient):
        """未授权访问风格偏好接口时返回 401。"""
        resp = client.get(STYLES_URL)
        assert resp.status_code == 401

    async def test_get_my_languages_unauthorized(self, client: TestClient):
        """未授权访问语言偏好接口时返回 401。"""
        resp = client.get(LANGUAGES_URL)
        assert resp.status_code == 401

    async def test_empty_data_clears_style_and_language_preferences(
        self, client: TestClient, db_session: AsyncSession
    ):
        """清空听歌历史和歌单后，风格与语言偏好应被清空。"""
        user = await _create_user(db_session, "pref_empty_clear")
        style = Style(name="Blues")
        language = Language(name="Spanish")
        db_session.add_all([style, language])
        await db_session.commit()
        await db_session.refresh(style)
        await db_session.refresh(language)

        db_session.add(UserStyle(user_id=user.id, style_id=style.id))
        db_session.add(UserLanguage(user_id=user.id, language_id=language.id))
        await db_session.commit()

        await recalculate_user_tags(db_session, user.id)

        styles = list(
            (await db_session.execute(select(UserStyle).where(UserStyle.user_id == user.id)))
            .scalars()
            .all()
        )
        languages = list(
            (await db_session.execute(select(UserLanguage).where(UserLanguage.user_id == user.id)))
            .scalars()
            .all()
        )
        assert styles == []
        assert languages == []

    async def test_recalculate_overwrites_existing_style_and_language_preferences(
        self, client: TestClient, db_session: AsyncSession
    ):
        """重新计算后，旧的风格与语言偏好应被新偏好覆盖。"""
        user = await _create_user(db_session, "pref_overwrite")
        old_style = Style(name="OldStyle")
        new_style = Style(name="NewStyle")
        old_language = Language(name="OldLang")
        new_language = Language(name="NewLang")
        db_session.add_all([old_style, new_style, old_language, new_language])
        await db_session.commit()
        await db_session.refresh(old_style)
        await db_session.refresh(new_style)
        await db_session.refresh(old_language)
        await db_session.refresh(new_language)

        db_session.add(UserStyle(user_id=user.id, style_id=old_style.id))
        db_session.add(UserLanguage(user_id=user.id, language_id=old_language.id))
        await db_session.commit()

        music = await _create_music_with_tags(
            db_session,
            title="NewSong",
            style_id=new_style.id,
            language_id=new_language.id,
        )
        await _create_play_history_directly(db_session, user.id, music.id, play_count=1)
        await recalculate_user_tags(db_session, user.id)

        styles = list(
            (await db_session.execute(select(UserStyle).where(UserStyle.user_id == user.id)))
            .scalars()
            .all()
        )
        languages = list(
            (await db_session.execute(select(UserLanguage).where(UserLanguage.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(styles) == 1
        assert styles[0].style_id == new_style.id
        assert len(languages) == 1
        assert languages[0].language_id == new_language.id

    async def test_style_and_language_tie_at_fifth_place(
        self, client: TestClient, db_session: AsyncSession
    ):
        """第 5 名存在并列时，风格与语言偏好应保留超过 5 个。"""
        user = await _create_user(db_session, "pref_tie")
        styles = [Style(name=f"Style{i}") for i in range(1, 8)]
        languages = [Language(name=f"Lang{i}") for i in range(1, 8)]
        db_session.add_all(styles + languages)
        await db_session.commit()
        for s in styles:
            await db_session.refresh(s)
        for l in languages:
            await db_session.refresh(l)

        # 构造频率：style1=6, style2~6=2, style7=1 → 第 5 名频率=2，保留 6 个
        for idx, style in enumerate(styles):
            music = await _create_music_with_tags(
                db_session,
                title=f"TieStyleSong{idx}",
                style_id=style.id,
            )
            play_count = 6 if idx == 0 else (2 if idx < 6 else 1)
            await _create_play_history_directly(
                db_session, user.id, music.id, play_count=play_count
            )

        for idx, language in enumerate(languages):
            music = await _create_music_with_tags(
                db_session,
                title=f"TieLangSong{idx}",
                language_id=language.id,
            )
            play_count = 6 if idx == 0 else (2 if idx < 6 else 1)
            await _create_play_history_directly(
                db_session, user.id, music.id, play_count=play_count
            )

        await recalculate_user_tags(db_session, user.id)

        user_styles = list(
            (await db_session.execute(select(UserStyle).where(UserStyle.user_id == user.id)))
            .scalars()
            .all()
        )
        user_languages = list(
            (await db_session.execute(select(UserLanguage).where(UserLanguage.user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(user_styles) == 6
        assert len(user_languages) == 6

    async def test_auto_trigger_via_play_history_api_for_style_and_language(
        self, client: TestClient, db_session: AsyncSession
    ):
        """通过播放历史 API 记录播放后，风格与语言偏好应自动更新。"""
        user = await _create_user(db_session, "pref_auto_api")
        style = Style(name="Reggae")
        language = Language(name="Portuguese")
        db_session.add_all([style, language])
        await db_session.commit()
        await db_session.refresh(style)
        await db_session.refresh(language)

        music = await _create_music_with_tags(
            db_session,
            title="ReggaePortuguese",
            style_id=style.id,
            language_id=language.id,
        )

        resp = client.post(
            PLAY_HISTORY_URL + "/",
            headers=_auth_header(user),
            json={"music_id": music.id},
        )
        assert resp.status_code == 201

        resp = client.get(STYLES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == style.id

        resp = client.get(LANGUAGES_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tag_id"] == language.id
