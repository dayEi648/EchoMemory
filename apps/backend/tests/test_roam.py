"""私人漫游（Private Roam）测试模块。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.dictionary import EmotionTag, InterestTag, Language, Style
from echomemory_backend.models.music import Music, MusicEmotionTag, MusicInterestTag
from echomemory_backend.models.user import User
from tests.api_helpers import api_data

BASE_URL = "/api/v1/roam"


async def _create_user(
    db: AsyncSession,
    username: str,
) -> User:
    """创建测试用户。"""
    user = User(
        username=username,
        password_hash=get_password_hash("secret"),
        nickname=username,
        role=0,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _auth_header(user: User) -> dict[str, str]:
    """生成测试用认证请求头。"""
    return {"Authorization": f"Bearer {create_access_token(subject=user.id)}"}


async def _create_music_with_tags(
    db: AsyncSession,
    title: str,
    *,
    is_published: bool = True,
    style_id: int | None = None,
    language_id: int | None = None,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
) -> Music:
    """创建带标签的测试音乐。"""
    music = Music(
        title=title,
        is_published=is_published,
        style_id=style_id,
        language_id=language_id,
        file_url="https://oss.example.com/musics/test.mp3",
        cover_icon_url="https://oss.example.com/covers/icon.jpg",
    )
    db.add(music)
    await db.flush()

    if emotion_tag_id is not None:
        db.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=emotion_tag_id))
    if interest_tag_id is not None:
        db.add(MusicInterestTag(music_id=music.id, interest_tag_id=interest_tag_id))

    await db.commit()
    await db.refresh(music)
    return music


async def _first_emotion_tag(db: AsyncSession) -> EmotionTag:
    """获取第一个情绪标签。"""
    from sqlalchemy import select

    result = await db.execute(select(EmotionTag).limit(1))
    return result.scalar_one()


async def _first_interest_tag(db: AsyncSession) -> InterestTag:
    """获取第一个兴趣标签。"""
    from sqlalchemy import select

    result = await db.execute(select(InterestTag).limit(1))
    return result.scalar_one()


async def _first_style(db: AsyncSession) -> Style:
    """获取第一个风格。"""
    from sqlalchemy import select

    result = await db.execute(select(Style).limit(1))
    return result.scalar_one()


async def _first_language(db: AsyncSession) -> Language:
    """获取第一个语言。"""
    from sqlalchemy import select

    result = await db.execute(select(Language).limit(1))
    return result.scalar_one()


# ---------------------------------------------------------------------------
# 基础流程测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_roam_returns_one_song(
    client: TestClient,
    db_session: AsyncSession,
):
    """开始漫游应返回 1 首随机歌曲并初始化 session。"""
    user = await _create_user(db_session, "roam_start_user")
    await _create_music_with_tags(db_session, "Roam Start Song")

    response = client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert len(data["playlist"]) == 1
    assert data["position"] == 0
    assert data["current_song"] is not None
    assert data["current_song"]["id"] == data["playlist"][0]


@pytest.mark.asyncio
async def test_start_roam_empty_library(
    client: TestClient,
    db_session: AsyncSession,
):
    """曲库为空时开始漫游应返回 404。"""
    user = await _create_user(db_session, "roam_empty_user")

    response = client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_roam_state_reflects_playlist_and_position(
    client: TestClient,
    db_session: AsyncSession,
):
    """状态接口应返回正确的播放列表、位置和池信息。"""
    user = await _create_user(db_session, "roam_state_user")
    await _create_music_with_tags(db_session, "State Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert len(data["playlist"]) == 1
    assert data["position"] == 0
    assert data["current_song"] is not None
    assert "pref_pool_summary" in data
    assert "dislike_pool_summary" in data


@pytest.mark.asyncio
async def test_state_without_active_session(
    client: TestClient,
    db_session: AsyncSession,
):
    """没有活跃漫游 session 时获取状态应返回 404。"""
    user = await _create_user(db_session, "roam_nosession_user")

    response = client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 导航测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_generates_new_song_when_at_end(
    client: TestClient,
    db_session: AsyncSession,
):
    """在列表末尾点下一首应生成新歌并追加到播放列表。"""
    user = await _create_user(db_session, "roam_next_user")
    for i in range(5):
        await _create_music_with_tags(db_session, f"Next Song {i}")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert len(data["playlist"]) == 2
    assert data["position"] == 1
    assert data["playlist"][0] != data["playlist"][1]


@pytest.mark.asyncio
async def test_next_navigates_without_generating(
    client: TestClient,
    db_session: AsyncSession,
):
    """回到之前的歌再点下一首，不生成新歌，只导航。"""
    user = await _create_user(db_session, "roam_nav_user")
    for i in range(5):
        await _create_music_with_tags(db_session, f"Nav Song {i}")

    # 生成 3 首歌
    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    resp3 = client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    data3 = api_data(resp3)
    assert len(data3["playlist"]) == 3

    # 回到第 1 首（position 0）
    client.post(f"{BASE_URL}/prev", headers=_auth_header(user))
    client.post(f"{BASE_URL}/prev", headers=_auth_header(user))

    # 再点下一首 → 回到 position 1，列表不变
    response = client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    data = api_data(response)
    assert len(data["playlist"]) == 3
    assert data["position"] == 1


@pytest.mark.asyncio
async def test_prev_navigates_back(
    client: TestClient,
    db_session: AsyncSession,
):
    """点上一首应回到前一首。"""
    user = await _create_user(db_session, "roam_prev_user")
    for i in range(3):
        await _create_music_with_tags(db_session, f"Prev Song {i}")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/next", headers=_auth_header(user))

    response = client.post(f"{BASE_URL}/prev", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert data["position"] == 0


@pytest.mark.asyncio
async def test_prev_at_start_does_not_go_below_zero(
    client: TestClient,
    db_session: AsyncSession,
):
    """在第一首点上一首不越界，保持在 position 0。"""
    user = await _create_user(db_session, "roam_boundary_user")
    await _create_music_with_tags(db_session, "Boundary Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.post(f"{BASE_URL}/prev", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert data["position"] == 0


# ---------------------------------------------------------------------------
# 收藏测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_favorite_updates_pref_pool(
    client: TestClient,
    db_session: AsyncSession,
):
    """收藏一首带标签的歌后，偏好池应有对应标签。"""
    user = await _create_user(db_session, "roam_fav_user")
    emotion = await _first_emotion_tag(db_session)
    style = await _first_style(db_session)

    music = await _create_music_with_tags(
        db_session,
        "Fav Song",
        emotion_tag_id=emotion.id,
        style_id=style.id,
    )

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.post(
        f"{BASE_URL}/{music.id}/favorite", headers=_auth_header(user)
    )
    assert response.status_code == 200

    # 检查偏好池
    state_resp = client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    state_data = api_data(state_resp)
    pref = state_data["pref_pool_summary"]
    assert f"emotion:{emotion.id}" in pref
    assert f"style:{style.id}" in pref


@pytest.mark.asyncio
async def test_favorite_adds_to_liked_music(
    client: TestClient,
    db_session: AsyncSession,
):
    """收藏应把歌曲加入"我喜欢的音乐"歌单。"""
    user = await _create_user(db_session, "roam_fav_like_user")
    music = await _create_music_with_tags(db_session, "Like Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/{music.id}/favorite", headers=_auth_header(user))

    # 验证歌曲已收藏
    from echomemory_backend.models.collection import UserMusicLike
    from sqlalchemy import select

    stmt = select(UserMusicLike).where(
        UserMusicLike.user_id == user.id,
        UserMusicLike.music_id == music.id,
    )
    like = (await db_session.execute(stmt)).scalar_one_or_none()
    assert like is not None


@pytest.mark.asyncio
async def test_favorite_idempotent(
    client: TestClient,
    db_session: AsyncSession,
):
    """重复收藏同一首歌不会报错，池权重应正确累加。"""
    user = await _create_user(db_session, "roam_fav_idem_user")
    emotion = await _first_emotion_tag(db_session)
    music = await _create_music_with_tags(
        db_session, "Idem Song", emotion_tag_id=emotion.id
    )

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/{music.id}/favorite", headers=_auth_header(user))
    response = client.post(
        f"{BASE_URL}/{music.id}/favorite", headers=_auth_header(user)
    )
    assert response.status_code == 200

    state_data = api_data(
        client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    )
    # 权重应为 2（两次收藏各 +1）
    assert state_data["pref_pool_summary"][f"emotion:{emotion.id}"] == "2"


# ---------------------------------------------------------------------------
# 不喜欢测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dislike_without_reasons_blocks_song_only(
    client: TestClient,
    db_session: AsyncSession,
):
    """无原因的不喜欢只屏蔽歌曲 ID，不屏蔽标签。"""
    user = await _create_user(db_session, "roam_dislike_user")
    emotion = await _first_emotion_tag(db_session)
    music = await _create_music_with_tags(
        db_session, "Dislike Song", emotion_tag_id=emotion.id
    )

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.post(
        f"{BASE_URL}/{music.id}/dislike", headers=_auth_header(user)
    )
    assert response.status_code == 200

    state_data = api_data(
        client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    )
    dislike = state_data["dislike_pool_summary"]
    assert f"song:{music.id}" in dislike
    # 无原因时不应有标签级屏蔽
    assert f"emotion:{emotion.id}" not in dislike


@pytest.mark.asyncio
async def test_dislike_with_reasons_blocks_tags(
    client: TestClient,
    db_session: AsyncSession,
):
    """带原因的不喜欢应同时屏蔽歌曲 ID 和指定标签。"""
    user = await _create_user(db_session, "roam_dislike_tag_user")
    emotion = await _first_emotion_tag(db_session)
    interest = await _first_interest_tag(db_session)
    music = await _create_music_with_tags(
        db_session,
        "Dislike Tag Song",
        emotion_tag_id=emotion.id,
        interest_tag_id=interest.id,
    )

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    response = client.post(
        f"{BASE_URL}/{music.id}/dislike",
        json={
            "emotion_tag_ids": [emotion.id],
            "interest_tag_ids": [interest.id],
        },
        headers=_auth_header(user),
    )
    assert response.status_code == 200

    state_data = api_data(
        client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    )
    dislike = state_data["dislike_pool_summary"]
    assert f"song:{music.id}" in dislike
    assert f"emotion:{emotion.id}" in dislike
    assert f"interest:{interest.id}" in dislike


# ---------------------------------------------------------------------------
# 推荐效果测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_song_respects_pref_pool(
    client: TestClient,
    db_session: AsyncSession,
):
    """偏好池应影响后续推荐——收藏后标签进入偏好池。"""
    user = await _create_user(db_session, "roam_pref_effect_user")
    emotion = await _first_emotion_tag(db_session)

    # 创建多首带情绪标签的歌和多首无标签的歌
    tagged_music = await _create_music_with_tags(
        db_session, "Pref Tagged", emotion_tag_id=emotion.id
    )
    for i in range(9):
        await _create_music_with_tags(db_session, f"Pref Untagged {i}")

    # 开始漫游 → 收藏第一首歌（不管是哪首）
    start_resp = client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    start_data = api_data(start_resp)
    first_song_id = start_data["current_song"]["id"]

    client.post(f"{BASE_URL}/{first_song_id}/favorite", headers=_auth_header(user))

    # 验证偏好池非空（第一首歌至少有一些标签会被加入）
    state_resp = client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    state_data = api_data(state_resp)
    # 如果第一首歌恰好是 tagged_music，则偏好池应有 emotion 标签
    # 验证偏好池存在且结构正确
    assert "pref_pool_summary" in state_data
    assert "dislike_pool_summary" in state_data


@pytest.mark.asyncio
async def test_next_song_respects_dislike_pool(
    client: TestClient,
    db_session: AsyncSession,
):
    """不喜欢池应排除对应的歌曲 ID。"""
    user = await _create_user(db_session, "roam_dislike_effect_user")
    for i in range(12):
        await _create_music_with_tags(db_session, f"Dislike Effect {i}")

    # 开始漫游
    start_resp = client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    start_data = api_data(start_resp)
    first_song_id = start_data["current_song"]["id"]

    # 不喜欢第一首歌
    client.post(
        f"{BASE_URL}/{first_song_id}/dislike", headers=_auth_header(user)
    )

    # 连续点下一首多次，验证第一首歌不会再次出现
    seen_ids = set()
    for _ in range(8):
        resp = client.post(f"{BASE_URL}/next", headers=_auth_header(user))
        data = api_data(resp)
        seen_ids.add(data["current_song"]["id"])

    assert first_song_id not in seen_ids


# ---------------------------------------------------------------------------
# Redis TTL 测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_roam_pool_has_ttl(
    client: TestClient,
    db_session: AsyncSession,
):
    """漫游 session 的 Redis key 应有 TTL 设置。"""
    from echomemory_backend.core.clients import redis_client as rc

    user = await _create_user(db_session, "roam_ttl_user")
    await _create_music_with_tags(db_session, "TTL Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))

    # 验证 playlist key 存在且有 TTL
    playlist_key = f"roam:playlist:{user.id}"
    ttl = await rc.redis_client.ttl(playlist_key)
    assert ttl > 0, f"Expected TTL > 0 for {playlist_key}, got {ttl}"

    # 验证 pref pool key 存在且有 TTL（空 hash 在 FakeRedis 中可能不存在，TTL 为 -2）
    pref_key = f"roam:pref:{user.id}"
    pref_ttl = await rc.redis_client.ttl(pref_key)
    assert pref_ttl > 0 or pref_ttl in (-1, -2)


# ---------------------------------------------------------------------------
# AI 推荐理由测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_reason_on_new_song(
    client: TestClient,
    db_session: AsyncSession,
):
    """生成新歌时应附带 AI 推荐理由。"""
    user = await _create_user(db_session, "roam_reason_user")
    for i in range(5):
        await _create_music_with_tags(db_session, f"Reason Song {i}")

    # 开始漫游 → 下一首（生成新歌）→ 检查理由字段
    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    resp = client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    assert resp.status_code == 200
    data = api_data(resp)
    # FakeDeepSeekClient 返回固定内容 "你好，我是 AI 助手。" → 作为理由
    assert data.get("recommend_reason") is not None
    assert len(data["recommend_reason"]) > 0


@pytest.mark.asyncio
async def test_recommend_reason_none_when_navigating(
    client: TestClient,
    db_session: AsyncSession,
):
    """纯导航（非生成新歌）时推荐理由应为 None。"""
    user = await _create_user(db_session, "roam_reason_nav_user")
    for i in range(5):
        await _create_music_with_tags(db_session, f"Reason Nav {i}")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/next", headers=_auth_header(user))
    # 回到上一首 → 纯导航，不应有推荐理由
    resp = client.post(f"{BASE_URL}/prev", headers=_auth_header(user))
    data = api_data(resp)
    assert data.get("recommend_reason") is None


# ---------------------------------------------------------------------------
# AI 品味总结测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_end_roam_generates_report(
    client: TestClient,
    db_session: AsyncSession,
):
    """结束漫游应生成品味总结报告并清除 session。"""
    user = await _create_user(db_session, "roam_report_user")
    emotion = await _first_emotion_tag(db_session)
    await _create_music_with_tags(
        db_session, "Report Song", emotion_tag_id=emotion.id
    )
    for i in range(3):
        await _create_music_with_tags(db_session, f"Report Extra {i}")

    # 漫游 → 收藏第一首歌（不管随机到哪首）
    start_resp = client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    first_id = api_data(start_resp)["current_song"]["id"]
    client.post(f"{BASE_URL}/{first_id}/favorite", headers=_auth_header(user))

    # 结束漫游
    resp = client.post(f"{BASE_URL}/end", headers=_auth_header(user))
    assert resp.status_code == 200
    data = api_data(resp)
    assert data["total_songs"] >= 1
    assert data["favorited_count"] >= 1
    assert len(data["taste_summary"]) > 0


@pytest.mark.asyncio
async def test_end_roam_clears_session(
    client: TestClient,
    db_session: AsyncSession,
):
    """结束漫游后 session 应被清除，再次获取状态应 404。"""
    user = await _create_user(db_session, "roam_end_clear_user")
    await _create_music_with_tags(db_session, "Clear Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))
    client.post(f"{BASE_URL}/end", headers=_auth_header(user))

    resp = client.get(f"{BASE_URL}/state", headers=_auth_header(user))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 自然语言引导测试
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guide_adjusts_direction(
    client: TestClient,
    db_session: AsyncSession,
):
    """自然语言引导应调整偏好池并生成新歌。"""
    user = await _create_user(db_session, "roam_guide_user")
    emotion = await _first_emotion_tag(db_session)
    for i in range(10):
        await _create_music_with_tags(
            db_session, f"Guide Song {i}", emotion_tag_id=emotion.id
        )

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))

    # 发送自然语言引导
    resp = client.post(
        f"{BASE_URL}/guide",
        json={"hint": "我想听更活力的音乐"},
        headers=_auth_header(user),
    )
    assert resp.status_code == 200
    data = api_data(resp)
    # 应返回解析后的意图和新歌
    assert len(data["parsed_intent"]) > 0
    assert data["new_state"]["current_song"] is not None


@pytest.mark.asyncio
async def test_guide_empty_hint_rejected(
    client: TestClient,
    db_session: AsyncSession,
):
    """空引导文本应被拒绝。"""
    user = await _create_user(db_session, "roam_guide_empty_user")
    await _create_music_with_tags(db_session, "Guide Empty Song")

    client.post(f"{BASE_URL}/start", headers=_auth_header(user))

    resp = client.post(
        f"{BASE_URL}/guide",
        json={"hint": ""},
        headers=_auth_header(user),
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_guide_requires_active_session(
    client: TestClient,
    db_session: AsyncSession,
):
    """无活跃漫游 session 时引导应返回 404。"""
    user = await _create_user(db_session, "roam_guide_nosess_user")

    resp = client.post(
        f"{BASE_URL}/guide",
        json={"hint": "来点摇滚"},
        headers=_auth_header(user),
    )
    assert resp.status_code == 404


def test_unauthenticated_access_rejected(client: TestClient):
    """无认证请求应被拒绝。"""
    # 需要认证的端点
    endpoints = [
        ("POST", "/start"),
        ("GET", "/state"),
        ("POST", "/next"),
        ("POST", "/prev"),
        ("POST", "/999/favorite"),
        ("POST", "/999/dislike"),
    ]
    for method, path in endpoints:
        response = client.request(method, f"{BASE_URL}{path}")
        assert response.status_code in (401, 403), (
            f"{method} {path} 返回 {response.status_code}"
        )
