from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security import create_access_token, get_password_hash
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistEmotionTag, PlaylistInterestTag
from echomemory_backend.models.user import User
from echomemory_backend.models.user_tag import UserEmotionTag, UserInterestTag
from echomemory_backend.services.user_tag_service import recalculate_user_tags

BASE = "/api/v1/users"
EMOTION_TAGS_URL = f"{BASE}/me/emotion-tags"
INTEREST_TAGS_URL = f"{BASE}/me/interest-tags"
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
    emotion_tag_ids: list[int] | None = None,
    interest_tag_ids: list[int] | None = None,
) -> Music:
    music = Music(
        title=title,
        is_published=True,
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
    db: AsyncSession, user_id: int, music_id: int
) -> PlayHistory:
    history = PlayHistory(user_id=user_id, music_id=music_id)
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


class TestEmotionTags:
    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "empty_emotion")
        resp = client.get(EMOTION_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
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
        resp = client.get(EMOTION_TAGS_URL)
        assert resp.status_code == 401


class TestInterestTags:
    async def test_empty_list(self, client: TestClient, db_session: AsyncSession):
        user = await _create_user(db_session, "empty_interest")
        resp = client.get(INTEREST_TAGS_URL, headers=_auth_header(user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tags(self, client: TestClient, db_session: AsyncSession):
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
        resp = client.get(INTEREST_TAGS_URL)
        assert resp.status_code == 401


class TestRecalculateUserTags:
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
        resp = client.post(RECALCULATE_URL)
        assert resp.status_code == 401
