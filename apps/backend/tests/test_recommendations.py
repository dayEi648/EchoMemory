"""推荐系统测试模块。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.security.security import create_access_token, get_password_hash
from echomemory_backend.models.album import (
    Album,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
)
from echomemory_backend.models.dictionary import (
    EmotionTag,
    InterestTag,
    Language,
    Style,
)
from echomemory_backend.models.music import (
    Music,
    MusicEmotionTag,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.recommendation import (
    UserDailyRecommendation,
    UserRadarRecommendation,
)
from echomemory_backend.models.user import User
from echomemory_backend.services import playlist_service
from echomemory_backend.services.recommendation_service import (
    _today,
    refresh_all_daily_and_radar_recommendations,
)
from tests.api_helpers import api_data

BASE_URL = "/api/v1/recommendations"


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


async def _first_emotion_tag(db: AsyncSession) -> EmotionTag:
    """获取第一个情绪标签。"""
    result = await db.execute(select(EmotionTag).limit(1))
    tag = result.scalar_one()
    return tag


async def _first_interest_tag(db: AsyncSession) -> InterestTag:
    """获取第一个兴趣标签。"""
    result = await db.execute(select(InterestTag).limit(1))
    tag = result.scalar_one()
    return tag


async def _first_style(db: AsyncSession) -> Style:
    """获取第一个风格。"""
    result = await db.execute(select(Style).limit(1))
    style = result.scalar_one()
    return style


async def _first_language(db: AsyncSession) -> Language:
    """获取第一个语言。"""
    result = await db.execute(select(Language).limit(1))
    language = result.scalar_one()
    return language


async def _create_music_directly(
    db: AsyncSession,
    title: str,
    *,
    is_published: bool = True,
    style_id: int | None = None,
    language_id: int | None = None,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
) -> Music:
    """直接创建测试音乐，可附加风格/语言/标签。"""
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


async def _collect_music_for_user(
    db: AsyncSession,
    user_id: int,
    music_id: int,
) -> None:
    """将音乐加入用户的默认喜欢歌单以模拟收藏，并触发用户标签重算。"""
    like_playlist = await playlist_service.create_default_like_playlist(
        db, user_id, commit=False
    )
    await playlist_service.add_music_to_playlist(db, like_playlist.id, music_id)


async def _create_public_playlist(
    db: AsyncSession,
    user_id: int,
    title: str,
    music_id: int,
    *,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    hot: int = 0,
) -> Playlist:
    """创建公开测试歌单并加入一首音乐，可附加标签与热度。"""
    playlist = Playlist(
        title=title,
        user_id=user_id,
        is_private=False,
        is_like=False,
        hot=hot,
    )
    db.add(playlist)
    await db.flush()

    db.add(PlaylistMusic(playlist_id=playlist.id, music_id=music_id, ordinal=0))
    if emotion_tag_id is not None:
        db.add(
            PlaylistEmotionTag(
                playlist_id=playlist.id, emotion_tag_id=emotion_tag_id
            )
        )
    if interest_tag_id is not None:
        db.add(
            PlaylistInterestTag(
                playlist_id=playlist.id, interest_tag_id=interest_tag_id
            )
        )

    await db.commit()
    await db.refresh(playlist)
    return playlist


async def _create_album(
    db: AsyncSession,
    title: str,
    music_id: int,
    *,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    hot: int = 0,
) -> Album:
    """创建测试专辑并加入一首音乐，可附加标签与热度。"""
    album = Album(title=title, hot=hot)
    db.add(album)
    await db.flush()

    db.add(AlbumMusic(album_id=album.id, music_id=music_id, ordinal=0))
    if emotion_tag_id is not None:
        db.add(AlbumEmotionTag(album_id=album.id, emotion_tag_id=emotion_tag_id))
    if interest_tag_id is not None:
        db.add(AlbumInterestTag(album_id=album.id, interest_tag_id=interest_tag_id))

    await db.commit()
    await db.refresh(album)
    return album


@pytest.mark.asyncio
async def test_daily_recommendations_up_to_10_and_deduped(
    client: TestClient,
    db_session: AsyncSession,
):
    """每日推荐应返回最多 10 首、互不重复且全部已上架的音乐。"""
    user = await _create_user(db_session, "daily_user")
    emotion = await _first_emotion_tag(db_session)
    interest = await _first_interest_tag(db_session)
    style = await _first_style(db_session)
    language = await _first_language(db_session)

    # 创建 12 首带各种标签的音乐
    musics = []
    for i in range(12):
        music = await _create_music_directly(
            db_session,
            f"Daily Song {i}",
            style_id=style.id if i % 4 == 0 else None,
            language_id=language.id if i % 4 == 1 else None,
            emotion_tag_id=emotion.id if i % 4 == 2 else None,
            interest_tag_id=interest.id if i % 4 == 3 else None,
        )
        musics.append(music)

    # 收藏一首音乐以触发用户标签更新，确保用户有画像
    await _collect_music_for_user(db_session, user.id, musics[0].id)

    response = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    items = data["items"]
    assert len(items) <= 10
    assert len({m["id"] for m in items}) == len(items)
    for item in items:
        assert item["is_collected_by_me"] is not None


@pytest.mark.asyncio
async def test_daily_recommendations_cold_start(
    client: TestClient,
    db_session: AsyncSession,
):
    """新用户无任何标签时，每日推荐应从全库兜底并正常返回。"""
    user = await _create_user(db_session, "cold_user")
    for i in range(5):
        await _create_music_directly(db_session, f"Cold Song {i}")

    response = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    assert 1 <= len(data["items"]) <= 5


@pytest.mark.asyncio
async def test_radar_recommendations_up_to_20_unique(
    client: TestClient,
    db_session: AsyncSession,
):
    """私人雷达应返回最多 20 首互不重复的音乐。"""
    user = await _create_user(db_session, "radar_user")
    emotion = await _first_emotion_tag(db_session)
    style = await _first_style(db_session)

    musics = []
    for i in range(25):
        music = await _create_music_directly(
            db_session,
            f"Radar Song {i}",
            emotion_tag_id=emotion.id if i % 2 == 0 else None,
            style_id=style.id if i % 3 == 0 else None,
        )
        musics.append(music)

    # 收藏 3 首，触发用户画像
    for music in musics[:3]:
        await _collect_music_for_user(db_session, user.id, music.id)

    response = client.get(f"{BASE_URL}/radar", headers=_auth_header(user))
    assert response.status_code == 200
    data = api_data(response)
    items = data["items"]
    assert len(items) == 20
    assert len({m["id"] for m in items}) == 20


@pytest.mark.asyncio
async def test_recommendation_chart_counts_users(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐榜应按用户去重统计今日推荐次数。"""
    user1 = await _create_user(db_session, "chart_user1")
    user2 = await _create_user(db_session, "chart_user2")
    music = await _create_music_directly(db_session, "Chart Song")

    # 通过每日推荐生成让两个用户都包含这首歌
    from echomemory_backend.services.recommendation_service import (
        get_or_generate_daily_recommendations,
    )

    # 为两个用户强制生成，确保存在记录
    await get_or_generate_daily_recommendations(db_session, user1.id)
    await get_or_generate_daily_recommendations(db_session, user2.id)

    # 手动覆盖为指定歌曲以稳定测试
    from echomemory_backend.models.recommendation import UserDailyRecommendation

    for u in (user1, user2):
        row = await db_session.get(UserDailyRecommendation, (u.id,))
        # 通过 user_id + date 查询
        from sqlalchemy import select

        stmt = select(UserDailyRecommendation).where(
            UserDailyRecommendation.user_id == u.id
        )
        rec = (await db_session.execute(stmt)).scalar_one()
        rec.music_ids = [music.id]
    await db_session.commit()

    response = client.get(f"{BASE_URL}/chart")
    assert response.status_code == 200
    data = api_data(response)
    chart_item = next((m for m in data["items"] if m["id"] == music.id), None)
    assert chart_item is not None
    assert chart_item["recommend_count"] == 2


@pytest.mark.asyncio
async def test_recommended_playlists_excludes_own_and_private(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐歌单应排除用户自己的歌单和私密歌单。"""
    user = await _create_user(db_session, "playlist_user")
    other = await _create_user(db_session, "playlist_other")
    emotion = await _first_emotion_tag(db_session)

    music = await _create_music_directly(
        db_session, "Playlist Music", emotion_tag_id=emotion.id
    )

    # 自己的公开歌单
    await _create_public_playlist(
        db_session, user.id, "My Public Playlist", music.id
    )
    # 他人的公开歌单（带匹配标签）
    other_public = await _create_public_playlist(
        db_session,
        other.id,
        "Other Public Playlist",
        music.id,
        emotion_tag_id=emotion.id,
    )
    # 他人的私密歌单
    private_pl = Playlist(
        title="Private Playlist",
        user_id=other.id,
        is_private=True,
        is_like=False,
    )
    db_session.add(private_pl)
    await db_session.flush()
    db_session.add(PlaylistMusic(playlist_id=private_pl.id, music_id=music.id))
    await db_session.commit()

    # 给用户加上相同标签的收藏，使其画像匹配他人公开歌单
    await _collect_music_for_user(db_session, user.id, music.id)

    response = client.get(
        f"{BASE_URL}/playlists?limit=20&offset=0", headers=_auth_header(user)
    )
    assert response.status_code == 200
    data = api_data(response)
    ids = {pl["id"] for pl in data["items"]}
    assert other_public.id in ids
    assert private_pl.id not in ids


@pytest.mark.asyncio
async def test_recommended_albums(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐专辑应返回带匹配标签的专辑。"""
    user = await _create_user(db_session, "album_user")
    emotion = await _first_emotion_tag(db_session)

    music = await _create_music_directly(
        db_session, "Album Music", emotion_tag_id=emotion.id
    )
    album = await _create_album(
        db_session, "Tagged Album", music.id, emotion_tag_id=emotion.id
    )

    await _collect_music_for_user(db_session, user.id, music.id)

    response = client.get(
        f"{BASE_URL}/albums?limit=20&offset=0", headers=_auth_header(user)
    )
    assert response.status_code == 200
    data = api_data(response)
    ids = {a["id"] for a in data["items"]}
    assert album.id in ids
@pytest.mark.asyncio
async def test_daily_recommendations_idempotent(
    client: TestClient,
    db_session: AsyncSession,
):
    """同一用户重复调用每日推荐应返回相同结果且数据库仅保存一行。"""
    user = await _create_user(db_session, "daily_idempotent")
    for i in range(5):
        await _create_music_directly(db_session, f"Daily Idem {i}")

    response1 = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))
    response2 = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert api_data(response1)["items"] == api_data(response2)["items"]

    rows = (
        await db_session.execute(
            select(UserDailyRecommendation).where(
                UserDailyRecommendation.user_id == user.id,
                UserDailyRecommendation.date == _today(),
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_daily_recommendations_empty(
    client: TestClient,
    db_session: AsyncSession,
):
    """曲库为空时每日推荐应返回空列表。"""
    user = await _create_user(db_session, "daily_empty")

    response = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))

    assert response.status_code == 200
    data = api_data(response)
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_daily_recommendations_collected_flag(
    client: TestClient,
    db_session: AsyncSession,
):
    """每日推荐应正确返回音乐的当前用户收藏状态。"""
    user = await _create_user(db_session, "daily_collected")
    music = await _create_music_directly(db_session, "Collected Song")
    await _collect_music_for_user(db_session, user.id, music.id)

    response = client.get(f"{BASE_URL}/daily", headers=_auth_header(user))

    assert response.status_code == 200
    data = api_data(response)
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == music.id
    assert data["items"][0]["is_collected_by_me"] is True


@pytest.mark.asyncio
async def test_radar_recommendations_idempotent(
    client: TestClient,
    db_session: AsyncSession,
):
    """同一用户重复调用私人雷达应返回相同结果且数据库仅保存一行。"""
    user = await _create_user(db_session, "radar_idempotent")
    for i in range(5):
        await _create_music_directly(db_session, f"Radar Idem {i}")

    response1 = client.get(f"{BASE_URL}/radar", headers=_auth_header(user))
    response2 = client.get(f"{BASE_URL}/radar", headers=_auth_header(user))

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert api_data(response1)["items"] == api_data(response2)["items"]

    rows = (
        await db_session.execute(
            select(UserRadarRecommendation).where(
                UserRadarRecommendation.user_id == user.id,
                UserRadarRecommendation.date == _today(),
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_radar_recommendations_no_tags(
    client: TestClient,
    db_session: AsyncSession,
):
    """无用户画像时私人雷达应从全库兜底返回。"""
    user = await _create_user(db_session, "radar_no_tags")
    created_ids = []
    for i in range(5):
        music = await _create_music_directly(db_session, f"Radar No Tag {i}")
        created_ids.append(music.id)

    response = client.get(f"{BASE_URL}/radar", headers=_auth_header(user))

    assert response.status_code == 200
    data = api_data(response)
    assert len(data["items"]) == 5
    returned_ids = {m["id"] for m in data["items"]}
    assert returned_ids == set(created_ids)


@pytest.mark.asyncio
async def test_radar_limits_collected_to_ten(
    client: TestClient,
    db_session: AsyncSession,
):
    """私人雷达中来自已收藏音乐的数量不应超过 10 首。"""
    user = await _create_user(db_session, "radar_many_collected")
    musics = []
    for i in range(25):
        music = await _create_music_directly(db_session, f"Radar Many {i}")
        musics.append(music)

    for music in musics[:12]:
        await _collect_music_for_user(db_session, user.id, music.id)

    response = client.get(f"{BASE_URL}/radar", headers=_auth_header(user))

    assert response.status_code == 200
    data = api_data(response)
    assert len(data["items"]) == 20
    collected_in_result = {
        m["id"] for m in data["items"] if m["is_collected_by_me"]
    }
    assert len(collected_in_result) <= 10
    assert collected_in_result.issubset({m.id for m in musics[:12]})


@pytest.mark.asyncio
async def test_recommended_playlists_pagination_crosses_fallback(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐歌单在标签匹配与兜底池边界处分页不应出现重复或遗漏。"""
    user = await _create_user(db_session, "playlist_paginator")
    other = await _create_user(db_session, "playlist_paginator_other")
    emotion = await _first_emotion_tag(db_session)
    music = await _create_music_directly(
        db_session, "Paginator Music", emotion_tag_id=emotion.id
    )

    tag_playlists = []
    for i in range(3):
        pl = await _create_public_playlist(
            db_session,
            other.id,
            f"Tag Playlist {i}",
            music.id,
            emotion_tag_id=emotion.id,
        )
        tag_playlists.append(pl)

    fallback_playlists = []
    for i in range(3):
        pl = await _create_public_playlist(
            db_session,
            other.id,
            f"Fallback Playlist {i}",
            music.id,
        )
        fallback_playlists.append(pl)

    await _collect_music_for_user(db_session, user.id, music.id)

    all_ids = {pl.id for pl in tag_playlists + fallback_playlists}
    returned_ids: set[int] = set()
    for offset in (0, 2, 4):
        response = client.get(
            f"{BASE_URL}/playlists?limit=2&offset={offset}",
            headers=_auth_header(user),
        )
        assert response.status_code == 200
        data = api_data(response)
        assert len(data["items"]) <= 2
        assert data["total"] == 6
        returned_ids.update(pl["id"] for pl in data["items"])

    assert returned_ids == all_ids


@pytest.mark.asyncio
async def test_recommended_albums_pagination_crosses_fallback(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐专辑在标签匹配与兜底池边界处分页不应出现重复或遗漏。"""
    user = await _create_user(db_session, "album_paginator")
    emotion = await _first_emotion_tag(db_session)
    music = await _create_music_directly(
        db_session, "Paginator Album Music", emotion_tag_id=emotion.id
    )

    tag_albums = []
    for i in range(3):
        album_music = await _create_music_directly(
            db_session, f"Tag Album Music {i}", emotion_tag_id=emotion.id
        )
        album = await _create_album(
            db_session,
            f"Tag Album {i}",
            album_music.id,
            emotion_tag_id=emotion.id,
        )
        tag_albums.append(album)

    fallback_albums = []
    for i in range(3):
        album_music = await _create_music_directly(
            db_session, f"Fallback Album Music {i}"
        )
        album = await _create_album(
            db_session,
            f"Fallback Album {i}",
            album_music.id,
        )
        fallback_albums.append(album)

    await _collect_music_for_user(db_session, user.id, music.id)

    all_ids = {album.id for album in tag_albums + fallback_albums}
    returned_ids: set[int] = set()
    for offset in (0, 2, 4):
        response = client.get(
            f"{BASE_URL}/albums?limit=2&offset={offset}",
            headers=_auth_header(user),
        )
        assert response.status_code == 200
        data = api_data(response)
        assert len(data["items"]) <= 2
        assert data["total"] == 6
        returned_ids.update(a["id"] for a in data["items"])

    assert returned_ids == all_ids


@pytest.mark.asyncio
async def test_recommendation_chart_distinct_and_published(
    client: TestClient,
    db_session: AsyncSession,
):
    """推荐榜应按用户去重计数，并排除未上架音乐。"""
    user1 = await _create_user(db_session, "chart_distinct_1")
    user2 = await _create_user(db_session, "chart_distinct_2")
    published = await _create_music_directly(db_session, "Chart Published")
    unpublished = await _create_music_directly(
        db_session, "Chart Unpublished", is_published=False
    )

    today = _today()
    db_session.add(
        UserDailyRecommendation(
            user_id=user1.id,
            date=today,
            music_ids=[published.id, published.id],
        )
    )
    db_session.add(
        UserDailyRecommendation(
            user_id=user2.id,
            date=today,
            music_ids=[published.id, unpublished.id],
        )
    )
    await db_session.commit()

    response = client.get(f"{BASE_URL}/chart")

    assert response.status_code == 200
    data = api_data(response)
    chart_item = next((m for m in data["items"] if m["id"] == published.id), None)
    assert chart_item is not None
    assert chart_item["recommend_count"] == 2
    assert not any(m["id"] == unpublished.id for m in data["items"])


@pytest.mark.asyncio
async def test_refresh_all_daily_and_radar(
    client: TestClient,
    db_session: AsyncSession,
):
    """批量刷新应为所有活跃用户生成每日推荐与私人雷达。"""
    user1 = await _create_user(db_session, "refresh_user_1")
    user2 = await _create_user(db_session, "refresh_user_2")
    for i in range(3):
        await _create_music_directly(db_session, f"Refresh Music {i}")

    result = await refresh_all_daily_and_radar_recommendations(db_session)

    assert result["daily"] == 2
    assert result["radar"] == 2

    today = _today()
    daily_rows = (
        await db_session.execute(
            select(UserDailyRecommendation).where(
                UserDailyRecommendation.date == today
            )
        )
    ).scalars().all()
    radar_rows = (
        await db_session.execute(
            select(UserRadarRecommendation).where(
                UserRadarRecommendation.date == today
            )
        )
    ).scalars().all()
    assert len(daily_rows) == 2
    assert len(radar_rows) == 2


def test_recommendations_require_auth(client: TestClient):
    """每日推荐、雷达、歌单、专辑接口需要登录。"""
    for path in ("/daily", "/radar", "/playlists", "/albums"):
        response = client.get(f"{BASE_URL}{path}")
        assert response.status_code in (401, 403), f"{path} 返回 {response.status_code}"


def test_chart_no_auth(client: TestClient):
    """推荐榜允许未认证访问。"""
    response = client.get(f"{BASE_URL}/chart")
    assert response.status_code == 200
@pytest.mark.asyncio
async def test_recommended_playlists_fallback_by_hotness(
    client: TestClient,
    db_session: AsyncSession,
):
    """无标签匹配时，推荐歌单应按热度倒序兜底。"""
    user = await _create_user(db_session, "playlist_hot_user")
    other = await _create_user(db_session, "playlist_hot_other")
    music = await _create_music_directly(db_session, "Hot Music")

    low_hot = await _create_public_playlist(
        db_session, other.id, "Low Hot", music.id, hot=1
    )
    high_hot = await _create_public_playlist(
        db_session, other.id, "High Hot", music.id, hot=10
    )

    response = client.get(
        f"{BASE_URL}/playlists?limit=2", headers=_auth_header(user)
    )

    assert response.status_code == 200
    data = api_data(response)
    assert [pl["id"] for pl in data["items"]] == [high_hot.id, low_hot.id]


@pytest.mark.asyncio
async def test_recommended_playlists_broadens_to_own_when_no_others(
    client: TestClient,
    db_session: AsyncSession,
):
    """当没有其他用户公开歌单时，应放宽限制展示自己的公开歌单。"""
    user = await _create_user(db_session, "playlist_own_user")
    music = await _create_music_directly(db_session, "Own Music")
    own_playlist = await _create_public_playlist(
        db_session, user.id, "My Public Playlist", music.id, hot=5
    )

    response = client.get(
        f"{BASE_URL}/playlists?limit=10", headers=_auth_header(user)
    )

    assert response.status_code == 200
    data = api_data(response)
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == own_playlist.id


@pytest.mark.asyncio
async def test_recommended_albums_fallback_by_hotness(
    client: TestClient,
    db_session: AsyncSession,
):
    """无标签匹配时，推荐专辑应按热度倒序兜底。"""
    user = await _create_user(db_session, "album_hot_user")
    music1 = await _create_music_directly(db_session, "Album Hot Music 1")
    music2 = await _create_music_directly(db_session, "Album Hot Music 2")

    low_hot = await _create_album(
        db_session, "Low Hot Album", music1.id, hot=1
    )
    high_hot = await _create_album(
        db_session, "High Hot Album", music2.id, hot=10
    )

    response = client.get(
        f"{BASE_URL}/albums?limit=2", headers=_auth_header(user)
    )

    assert response.status_code == 200
    data = api_data(response)
    assert [a["id"] for a in data["items"]] == [high_hot.id, low_hot.id]


@pytest.mark.asyncio
async def test_recommended_albums_broadens_to_empty_albums(
    client: TestClient,
    db_session: AsyncSession,
):
    """当没有非空专辑时，应放宽限制展示空专辑，避免完全为空。"""
    user = await _create_user(db_session, "album_empty_user")
    empty_album = Album(title="Empty Album", hot=5)
    db_session.add(empty_album)
    await db_session.commit()
    await db_session.refresh(empty_album)

    response = client.get(
        f"{BASE_URL}/albums?limit=10", headers=_auth_header(user)
    )

    assert response.status_code == 200
    data = api_data(response)
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == empty_album.id
