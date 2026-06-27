"""私人漫游（Private Roam）核心业务服务。

基于 Redis 存储临时偏好/不喜欢池和播放列表，每天凌晨 4 点（UTC+8）
自动清空。冷启动纯随机，后续基于用户反馈加权推荐。
"""

from __future__ import annotations

import json
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.core.clients import redis_client as _rc
from echomemory_backend.core.config import settings
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInterestTag,
)

# 通过模块引用，确保测试 monkeypatch 生效
from echomemory_backend.ai.clients import deepseek as _deepseek_module
from echomemory_backend.ai.clients.deepseek import ChatMessage
from echomemory_backend.services.roam.prompts import (
    GUIDE_PROMPT,
    REASON_PROMPT,
    REPORT_PROMPT,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_ROAM_PREFIX = "roam"
_CANDIDATE_POOL_SIZE = 30
_SOFTMAX_TEMPERATURE = 0.5

# 评分权重
_SCORE_SONG_DISLIKE = -10.0
_SCORE_ARTIST_DISLIKE = -5.0
_SCORE_RANDOM_MAX = 3.0

# 池键后缀
_SUFFIX_PREF = "pref"
_SUFFIX_DISLIKE = "dislike"
_SUFFIX_PLAYLIST = "playlist"
_SUFFIX_POSITION = "position"
_SUFFIX_ACTIONS = "actions"
_SUFFIX_REASON = "reason"

# 标签键前缀
_TAG_EMOTION = "emotion"
_TAG_INTEREST = "interest"
_TAG_STYLE = "style"
_TAG_LANGUAGE = "language"
_TAG_INSTRUMENT = "instrument"
_TAG_ARTIST = "artist"
_TAG_SONG = "song"

# 默认权重增量
_DEFAULT_WEIGHT_INCREMENT = 1
_DEFAULT_DISLIKE_WEIGHT = -1

CST = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Redis key 工具
# ---------------------------------------------------------------------------


def _roam_key(user_id: int, suffix: str) -> str:
    """生成漫游 Redis key。"""
    return f"{_ROAM_PREFIX}:{suffix}:{user_id}"


def _seconds_until_4am_cst() -> int:
    """计算距离下一个 UTC+8 凌晨 4:00 的秒数。"""
    now = datetime.now(CST)
    target = now.replace(hour=4, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return max(1, int((target - now).total_seconds()))


async def _ensure_ttl(key: str) -> None:
    """为新 key 设置当天凌晨 4 点过期的 TTL。"""
    ttl = _seconds_until_4am_cst()
    await _rc.redis_client.expire(key, ttl)


# ---------------------------------------------------------------------------
# 音乐标签提取
# ---------------------------------------------------------------------------


async def _get_music_tag_ids(
    db: AsyncSession, music_id: int
) -> dict[str, list[str]]:
    """获取音乐的各类标签 ID（用于构建 pool key）。

    直接查询关联表，避免 ORM relationship lazy-load。

    Returns:
        {
            "emotion": ["emotion:1", "emotion:2"],
            "interest": ["interest:3"],
            "style": ["style:5"],
            "language": ["language:2"],
            "instrument": ["instrument:1"],
            "artist": ["artist:7"],
            "song": ["song:42"],
        }
    """
    # 查询 Music 基础字段（style_id, language_id）
    music_stmt = select(
        Music.id, Music.style_id, Music.language_id
    ).where(Music.id == music_id)
    music_row = (await db.execute(music_stmt)).one_or_none()

    if music_row is None:
        return {
            "emotion": [], "interest": [], "style": [], "language": [],
            "instrument": [], "artist": [], "song": [f"{_TAG_SONG}:{music_id}"],
        }

    # 查询情绪标签
    emotion_stmt = select(MusicEmotionTag.emotion_tag_id).where(
        MusicEmotionTag.music_id == music_id
    )
    emotion_rows = (await db.execute(emotion_stmt)).scalars().all()

    # 查询兴趣标签
    interest_stmt = select(MusicInterestTag.interest_tag_id).where(
        MusicInterestTag.music_id == music_id
    )
    interest_rows = (await db.execute(interest_stmt)).scalars().all()

    # 查询乐器
    from echomemory_backend.models.music import MusicInstrument
    instrument_stmt = select(MusicInstrument.instrument_id).where(
        MusicInstrument.music_id == music_id
    )
    instrument_rows = (await db.execute(instrument_stmt)).scalars().all()

    # 查询作者
    author_stmt = select(MusicAuthor.author_id).where(
        MusicAuthor.music_id == music_id
    )
    author_rows = (await db.execute(author_stmt)).scalars().all()

    tag_ids: dict[str, list[str]] = {
        "emotion": [f"{_TAG_EMOTION}:{tid}" for tid in emotion_rows],
        "interest": [f"{_TAG_INTEREST}:{tid}" for tid in interest_rows],
        "style": (
            [f"{_TAG_STYLE}:{music_row.style_id}"]
            if music_row.style_id is not None else []
        ),
        "language": (
            [f"{_TAG_LANGUAGE}:{music_row.language_id}"]
            if music_row.language_id is not None else []
        ),
        "instrument": [f"{_TAG_INSTRUMENT}:{iid}" for iid in instrument_rows],
        "artist": [f"{_TAG_ARTIST}:{aid}" for aid in author_rows],
        "song": [f"{_TAG_SONG}:{music_id}"],
    }
    return tag_ids


def _all_tag_keys(tag_ids: dict[str, list[str]]) -> list[str]:
    """展平所有标签 key 为单一列表（不含 song/artist 级）。"""
    keys: list[str] = []
    for category in ("emotion", "interest", "style", "language", "instrument"):
        keys.extend(tag_ids.get(category, []))
    return keys


# ---------------------------------------------------------------------------
# 加权评分与推荐
# ---------------------------------------------------------------------------


async def _score_candidates(
    db: AsyncSession,
    candidate_ids: list[int],
    pref_pool: dict[str, str],
    dislike_pool: dict[str, str],
) -> list[tuple[int, float]]:
    """对候选音乐进行加权评分。

    直接查询关联表，避免 ORM relationship lazy-load。

    Returns:
        [(music_id, score), ...] 按分数降序排列。
    """
    if not candidate_ids:
        return []

    # 1. 批量查询音乐基础信息
    music_stmt = select(Music.id, Music.style_id, Music.language_id).where(
        Music.id.in_(candidate_ids)
    )
    music_rows = (await db.execute(music_stmt)).all()
    music_map: dict[int, tuple[int | None, int | None]] = {
        row.id: (row.style_id, row.language_id) for row in music_rows
    }

    # 2. 批量查询情绪标签
    emotion_stmt = select(
        MusicEmotionTag.music_id, MusicEmotionTag.emotion_tag_id
    ).where(MusicEmotionTag.music_id.in_(candidate_ids))
    emotion_rows = (await db.execute(emotion_stmt)).all()
    emotion_map: dict[int, list[int]] = {mid: [] for mid in candidate_ids}
    for row in emotion_rows:
        emotion_map.setdefault(row.music_id, []).append(row.emotion_tag_id)

    # 3. 批量查询兴趣标签
    interest_stmt = select(
        MusicInterestTag.music_id, MusicInterestTag.interest_tag_id
    ).where(MusicInterestTag.music_id.in_(candidate_ids))
    interest_rows = (await db.execute(interest_stmt)).all()
    interest_map: dict[int, list[int]] = {mid: [] for mid in candidate_ids}
    for row in interest_rows:
        interest_map.setdefault(row.music_id, []).append(row.interest_tag_id)

    # 4. 批量查询乐器
    from echomemory_backend.models.music import MusicInstrument
    instrument_stmt = select(
        MusicInstrument.music_id, MusicInstrument.instrument_id
    ).where(MusicInstrument.music_id.in_(candidate_ids))
    instrument_rows = (await db.execute(instrument_stmt)).all()
    instrument_map: dict[int, list[int]] = {mid: [] for mid in candidate_ids}
    for row in instrument_rows:
        instrument_map.setdefault(row.music_id, []).append(row.instrument_id)

    # 5. 批量查询作者
    author_stmt = select(
        MusicAuthor.music_id, MusicAuthor.author_id
    ).where(MusicAuthor.music_id.in_(candidate_ids))
    author_rows = (await db.execute(author_stmt)).all()
    author_map: dict[int, list[int]] = {mid: [] for mid in candidate_ids}
    for row in author_rows:
        author_map.setdefault(row.music_id, []).append(row.author_id)

    # 6. 评分
    scored: list[tuple[int, float]] = []
    for music_id in candidate_ids:
        score = 0.0
        style_id, language_id = music_map.get(music_id, (None, None))

        # 偏好池匹配（正分）
        if style_id is not None:
            key = f"{_TAG_STYLE}:{style_id}"
            if key in pref_pool:
                score += float(pref_pool[key])
        if language_id is not None:
            key = f"{_TAG_LANGUAGE}:{language_id}"
            if key in pref_pool:
                score += float(pref_pool[key])
        for tid in emotion_map.get(music_id, []):
            key = f"{_TAG_EMOTION}:{tid}"
            if key in pref_pool:
                score += float(pref_pool[key])
        for tid in interest_map.get(music_id, []):
            key = f"{_TAG_INTEREST}:{tid}"
            if key in pref_pool:
                score += float(pref_pool[key])
        for iid in instrument_map.get(music_id, []):
            key = f"{_TAG_INSTRUMENT}:{iid}"
            if key in pref_pool:
                score += float(pref_pool[key])

        # 不喜欢池 - 歌曲级（大负分）
        if f"{_TAG_SONG}:{music_id}" in dislike_pool:
            score += _SCORE_SONG_DISLIKE

        # 不喜欢池 - 艺术家级（中等负分）
        for aid in author_map.get(music_id, []):
            if f"{_TAG_ARTIST}:{aid}" in dislike_pool:
                score += _SCORE_ARTIST_DISLIKE
                break

        # 不喜欢池 - 标签级
        if style_id is not None:
            key = f"{_TAG_STYLE}:{style_id}"
            if key in dislike_pool:
                score += float(dislike_pool[key])
        if language_id is not None:
            key = f"{_TAG_LANGUAGE}:{language_id}"
            if key in dislike_pool:
                score += float(dislike_pool[key])
        for tid in emotion_map.get(music_id, []):
            key = f"{_TAG_EMOTION}:{tid}"
            if key in dislike_pool:
                score += float(dislike_pool[key])
        for tid in interest_map.get(music_id, []):
            key = f"{_TAG_INTEREST}:{tid}"
            if key in dislike_pool:
                score += float(dislike_pool[key])
        for iid in instrument_map.get(music_id, []):
            key = f"{_TAG_INSTRUMENT}:{iid}"
            if key in dislike_pool:
                score += float(dislike_pool[key])

        # 随机探索因子
        score += random.uniform(0, _SCORE_RANDOM_MAX)

        scored.append((music_id, score))

    # 按分数降序
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _weighted_random_select(
    scored: list[tuple[int, float]], top_k: int = _CANDIDATE_POOL_SIZE
) -> int:
    """从评分列表中按 softmax 概率加权随机选择一首。

    取 top_k 候选，用 softmax 转换为概率分布后随机选一个。
    """
    if not scored:
        raise ValueError("scored list is empty")
    if len(scored) == 1:
        return scored[0][0]

    pool = scored[:top_k]
    scores = [s for _, s in pool]
    ids = [mid for mid, _ in pool]

    # Softmax with temperature
    max_score = max(scores)
    exp_scores = [
        math.exp((s - max_score) * _SOFTMAX_TEMPERATURE) for s in scores
    ]
    total = sum(exp_scores)
    if total == 0:
        return random.choice(ids)

    probs = [e / total for e in exp_scores]
    return random.choices(ids, weights=probs, k=1)[0]


async def _generate_next_song(
    db: AsyncSession,
    user_id: int,
    pref_pool: dict[str, str],
    dislike_pool: dict[str, str],
    exclude_ids: set[int],
) -> Music:
    """基于偏好和不喜���池加权随机推荐下一首歌。

    Args:
        db: 数据库 session。
        user_id: 用户 ID。
        pref_pool: 偏好池。
        dislike_pool: 不喜欢池。
        exclude_ids: 需排除的音乐 ID（已在播放列表中）。

    Returns:
        推荐的 Music 实例。

    Raises:
        BusinessError: 无可用候选歌曲时抛出。
    """
    # 先尝试从全库按标签评分
    from echomemory_backend.models.album import AlbumMusic

    # 获取所有已上架音乐 ID
    where_clause = [Music.is_published.is_(True)]
    if exclude_ids:
        where_clause.append(Music.id.not_in(list(exclude_ids)))

    stmt = select(Music.id).where(*where_clause)
    rows = await db.execute(stmt)
    all_ids = [row for row in rows.scalars().all()]

    if not all_ids:
        raise BusinessError(
            "No available music for roam",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    # 评分并加权随机选择
    scored = await _score_candidates(db, all_ids, pref_pool, dislike_pool)
    selected_id = _weighted_random_select(scored)

    # 加载完整 Music 实例（复用 _load_music_detail 确保所有关系 eager loaded）
    music = await _load_music_detail(db, selected_id)
    assert music is not None
    return music


async def _load_music_detail(
    db: AsyncSession, music_id: int
) -> Music | None:
    """加载音乐完整详情（含所有关联）。"""
    from echomemory_backend.models.album import AlbumMusic
    from echomemory_backend.models.music import MusicInstrument

    stmt = (
        select(Music)
        .where(Music.id == music_id)
        .options(
            selectinload(Music.style),
            selectinload(Music.language),
            selectinload(Music.emotion_tags).selectinload(MusicEmotionTag.emotion_tag),
            selectinload(Music.interest_tags).selectinload(MusicInterestTag.interest_tag),
            selectinload(Music.instruments).selectinload(MusicInstrument.instrument),
            selectinload(Music.authors).selectinload(MusicAuthor.author),
            selectinload(Music.album_musics).selectinload(AlbumMusic.album),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _check_collected(db: AsyncSession, user_id: int, music_id: int) -> bool:
    """检查用户是否已将该音乐收藏到任意歌单。"""
    from echomemory_backend.models.playlist import Playlist, PlaylistMusic

    stmt = (
        select(PlaylistMusic.music_id)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(
            Playlist.user_id == user_id,
            PlaylistMusic.music_id == music_id,
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return row is not None


async def _music_to_dict(db: AsyncSession, user_id: int, music: Music) -> dict:
    """将 Music ORM 实例转为 API 响应字典，附带用户喜欢状态。"""
    collected = await _check_collected(db, user_id, music.id)
    return _music_to_dict_raw(music, is_collected_by_me=collected)


def _music_to_dict_raw(music: Music, *, is_collected_by_me: bool = False) -> dict:
    """将 Music ORM 实例转为 API 响应字典。"""
    return {
        "id": music.id,
        "title": music.title,
        "is_vip": music.is_vip,
        "source": music.source,
        "style": (
            {"id": music.style.id, "name": music.style.name}
            if music.style
            else None
        ),
        "language": (
            {"id": music.language.id, "name": music.language.name}
            if music.language
            else None
        ),
        "collect_count": music.collect_count,
        "hot": music.hot,
        "comment_count": music.comment_count,
        "play_count": music.play_count,
        "is_published": music.is_published,
        "file_url": music.file_url,
        "lyrics_url": music.lyrics_url,
        "cover_icon_url": music.cover_icon_url,
        "cover_home_url": music.cover_home_url,
        "cover_play_url": music.cover_play_url,
        "release_date": (
            music.release_date.isoformat() if music.release_date else None
        ),
        "created_at": (
            music.created_at.isoformat() if music.created_at else None
        ),
        "updated_at": (
            music.updated_at.isoformat() if music.updated_at else None
        ),
        "authors": [
            {
                "id": a.author.id,
                "username": a.author.username,
                "nickname": a.author.nickname,
                "avatar_url": a.author.avatar_url,
                "ordinal": a.ordinal,
            }
            for a in music.authors
        ],
        "instruments": [
            {"id": i.instrument.id, "name": i.instrument.name}
            for i in music.instruments
        ],
        "emotion_tags": [
            {"id": t.emotion_tag.id, "name": t.emotion_tag.name}
            for t in music.emotion_tags
        ],
        "interest_tags": [
            {"id": t.interest_tag.id, "name": t.interest_tag.name}
            for t in music.interest_tags
        ],
        "album_musics": [
            {"id": am.album.id, "title": am.album.title}
            for am in music.album_musics
        ],
        "is_collected_by_me": is_collected_by_me,
    }


async def _read_pools(
    user_id: int,
) -> tuple[dict[str, str], dict[str, str]]:
    """从 Redis 读取偏好池和不喜欢池。"""
    pref_key = _roam_key(user_id, _SUFFIX_PREF)
    dislike_key = _roam_key(user_id, _SUFFIX_DISLIKE)
    pref = await _rc.redis_client.hgetall(pref_key)
    dislike = await _rc.redis_client.hgetall(dislike_key)
    return pref, dislike


async def _read_playlist(user_id: int) -> list[int]:
    """从 Redis 读取播放列表。"""
    key = _roam_key(user_id, _SUFFIX_PLAYLIST)
    raw = await _rc.redis_client.lrange(key, 0, -1)
    return [int(x) for x in raw]


async def _read_position(user_id: int) -> int:
    """从 Redis 读取当前播放位置。"""
    key = _roam_key(user_id, _SUFFIX_POSITION)
    raw = await _rc.redis_client.get(key)
    return int(raw) if raw is not None else 0


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


async def start_roam(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """开始新的漫游 session。

    清空旧 session（如有），纯随机生成第一首歌。

    Raises:
        BusinessError: 曲库为空时抛出 404。
    """
    # 清除旧 session
    for suffix in (_SUFFIX_PREF, _SUFFIX_DISLIKE, _SUFFIX_PLAYLIST, _SUFFIX_POSITION):
        await _rc.redis_client.delete(_roam_key(user_id, suffix))

    # 纯随机选第一首歌
    stmt = select(Music.id).where(Music.is_published.is_(True)).order_by(func.random()).limit(1)
    rows = await db.execute(stmt)
    first_id = rows.scalar_one_or_none()

    if first_id is None:
        raise BusinessError(
            "No music available for roam",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    music = await _load_music_detail(db, first_id)
    assert music is not None

    # 写入 Redis
    playlist_key = _roam_key(user_id, _SUFFIX_PLAYLIST)
    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    pref_key = _roam_key(user_id, _SUFFIX_PREF)
    dislike_key = _roam_key(user_id, _SUFFIX_DISLIKE)

    await _rc.redis_client.rpush(playlist_key, str(first_id))
    await _ensure_ttl(playlist_key)
    await _rc.redis_client.set(position_key, "0")
    await _ensure_ttl(position_key)
    # 初始化空池
    await _ensure_ttl(pref_key)
    await _ensure_ttl(dislike_key)

    return {
        "playlist": [first_id],
        "position": 0,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": {},
        "dislike_pool_summary": {},
    }


async def get_roam_state(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """获取当前漫游 session 完整状态。

    Raises:
        BusinessError: 无活跃 session 时抛出 404。
    """
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    position = await _read_position(user_id)
    pref, dislike = await _read_pools(user_id)

    current_id = playlist[position]
    music = await _load_music_detail(db, current_id)
    if music is None:
        raise BusinessError(
            "Roam music not found",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    return {
        "playlist": playlist,
        "position": position,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
        "recommend_reason": await _load_recommend_reason(user_id, current_id),
    }


async def next_song(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """下一首：导航到下一首或生成新歌。

    Raises:
        BusinessError: 无活跃 session 时抛出 404。
    """
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    position = await _read_position(user_id)

    if position < len(playlist) - 1:
        # 纯导航
        new_position = position + 1
    else:
        # 生成新歌
        pref, dislike = await _read_pools(user_id)
        exclude_ids = set(playlist)
        new_music = await _generate_next_song(
            db, user_id, pref, dislike, exclude_ids
        )
        playlist.append(new_music.id)
        playlist_key = _roam_key(user_id, _SUFFIX_PLAYLIST)
        await _rc.redis_client.rpush(playlist_key, str(new_music.id))
        new_position = len(playlist) - 1

    # 更新位置
    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    await _rc.redis_client.set(position_key, str(new_position))

    # 返回状态
    current_id = playlist[new_position]
    music = await _load_music_detail(db, current_id)
    assert music is not None

    pref, dislike = await _read_pools(user_id)
    return {
        "playlist": playlist,
        "position": new_position,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
    }


async def prev_song(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """上一首：纯导航。

    Raises:
        BusinessError: 无活跃 session 时抛出 404。
    """
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    position = await _read_position(user_id)
    new_position = max(0, position - 1)

    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    await _rc.redis_client.set(position_key, str(new_position))

    current_id = playlist[new_position]
    music = await _load_music_detail(db, current_id)
    assert music is not None

    pref, dislike = await _read_pools(user_id)
    return {
        "playlist": playlist,
        "position": new_position,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
    }


async def favorite_song(
    db: AsyncSession,
    user_id: int,
    song_id: int,
    *,
    playlist_id: int | None = None,
) -> dict:
    """收藏歌曲到指定歌单并更新偏好池。

    若未指定 playlist_id，默认收藏到"我喜欢的音乐"系统歌单。

    Raises:
        BusinessError: 歌曲不在当前播放列表中时抛出 400。
    """
    playlist = await _read_playlist(user_id)
    if song_id not in playlist:
        raise BusinessError(
            "Song not in current roam playlist",
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        )

    # 先获取标签 ID（commit 前），避免 commit 后 session 状态问题
    tag_ids = await _get_music_tag_ids(db, song_id)

    # 收藏到指定歌单或默认"我喜欢的音乐"
    from echomemory_backend.services import playlist_service

    try:
        if playlist_id is not None:
            await playlist_service.add_music_to_playlist(
                db, playlist_id, song_id, user_id, commit=False
            )
        else:
            like_playlist = await playlist_service.create_default_like_playlist(
                db, user_id, commit=False
            )
            await playlist_service.add_music_to_playlist(
                db, like_playlist.id, song_id, user_id, commit=False
            )
        await db.commit()
    except BusinessError as e:
        if e.code == ErrorCode.MUSIC_ALREADY_IN_PLAYLIST:
            # 已在该歌单中：只更新池，不报错
            await db.rollback()
        else:
            raise

    # 更新偏好池
    pref_key = _roam_key(user_id, _SUFFIX_PREF)
    for tag_key in _all_tag_keys(tag_ids):
        await _rc.redis_client.hincrby(pref_key, tag_key, _DEFAULT_WEIGHT_INCREMENT)
    await _ensure_ttl(pref_key)

    pref, dislike = await _read_pools(user_id)
    return {
        "success": True,
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
    }


async def dislike_song(
    user_id: int,
    song_id: int,
    reasons: dict | None = None,
) -> dict:
    """标记不喜欢并更新不喜欢池。

    - 默认：仅屏蔽歌曲 ID（权重 -10，歌曲级）。
    - 带 reasons 时：额外屏蔽指定标签（权重 -1，标签级）。

    Raises:
        BusinessError: 歌曲不在当前播放列表中时抛出 400。
    """
    playlist = await _read_playlist(user_id)
    if song_id not in playlist:
        raise BusinessError(
            "Song not in current roam playlist",
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        )

    dislike_key = _roam_key(user_id, _SUFFIX_DISLIKE)

    # 歌曲级标记
    await _rc.redis_client.hset(dislike_key, f"{_TAG_SONG}:{song_id}", "1")

    # 标签级原因
    if reasons:
        if reasons.get("emotion_tag_ids"):
            for tid in reasons["emotion_tag_ids"]:
                await _rc.redis_client.hincrby(
                    dislike_key,
                    f"{_TAG_EMOTION}:{tid}",
                    _DEFAULT_DISLIKE_WEIGHT,
                )
        if reasons.get("interest_tag_ids"):
            for tid in reasons["interest_tag_ids"]:
                await _rc.redis_client.hincrby(
                    dislike_key,
                    f"{_TAG_INTEREST}:{tid}",
                    _DEFAULT_DISLIKE_WEIGHT,
                )
        if reasons.get("style_id") is not None:
            await _rc.redis_client.hincrby(
                dislike_key,
                f"{_TAG_STYLE}:{reasons['style_id']}",
                _DEFAULT_DISLIKE_WEIGHT,
            )
        if reasons.get("language_id") is not None:
            await _rc.redis_client.hincrby(
                dislike_key,
                f"{_TAG_LANGUAGE}:{reasons['language_id']}",
                _DEFAULT_DISLIKE_WEIGHT,
            )

    await _ensure_ttl(dislike_key)

    pref, dislike = await _read_pools(user_id)
    return {
        "success": True,
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
    }


# ---------------------------------------------------------------------------
# 行为记录（供报告使用）
# ---------------------------------------------------------------------------


async def _record_action(user_id: int, action: str) -> None:
    """在 Redis 中记录一次漫游操作。"""
    key = _roam_key(user_id, _SUFFIX_ACTIONS)
    await _rc.redis_client.rpush(key, action)
    await _ensure_ttl(key)


async def _read_actions(user_id: int) -> list[str]:
    """读取漫游操作记录。"""
    key = _roam_key(user_id, _SUFFIX_ACTIONS)
    raw = await _rc.redis_client.lrange(key, 0, -1)
    return list(raw)


async def _clear_roam_session(user_id: int) -> None:
    """清除所有漫游 Redis key。"""
    for suffix in (
        _SUFFIX_PREF, _SUFFIX_DISLIKE, _SUFFIX_PLAYLIST,
        _SUFFIX_POSITION, _SUFFIX_ACTIONS, _SUFFIX_REASON,
    ):
        await _rc.redis_client.delete(_roam_key(user_id, suffix))


# ---------------------------------------------------------------------------
# AI 推荐理由
# ---------------------------------------------------------------------------


def _format_authors(music_dict: dict) -> str:
    """从 music dict 中提取作者名称字符串。"""
    authors = music_dict.get("authors", [])
    return ", ".join(a.get("nickname", "") or a.get("username", "") for a in authors)


def _describe_pool(pool: dict[str, str]) -> str:
    """将偏好/不喜欢池转换为可读摘要。"""
    if not pool:
        return "暂无偏好数据"
    parts = []
    for key, weight in pool.items():
        parts.append(f"{key}:{weight}")
    return ", ".join(parts[:20])  # 最多 20 项


async def _generate_recommend_reason(
    current_song: dict,
    pref_pool: dict[str, str],
    prev_song_title: str | None,
) -> str | None:
    """异步生成 AI 推荐理由，失败静默返回 None。"""
    try:
        client = _deepseek_module.DeepSeekClient(
            model=settings.deepseek_flash_model,
            enable_thinking=False,
        )
        prompt_data = {
            "当前歌曲": f"{current_song.get('title', '')} - {_format_authors(current_song)}",
            "风格": current_song.get("style", {}).get("name") if current_song.get("style") else None,
            "情绪标签": [t.get("name") for t in current_song.get("emotion_tags", [])],
            "用户偏好趋势": _describe_pool(pref_pool),
            "上一首歌": prev_song_title or "无（漫游刚开始）",
        }
        response = await client.chat(
            [
                ChatMessage(role="system", content=REASON_PROMPT),
                ChatMessage(
                    role="user",
                    content=json.dumps(prompt_data, ensure_ascii=False, default=str),
                ),
            ],
            temperature=0.7,
            max_tokens=60,
        )
        result = (response.content or "").strip()
        return result[:60] if result else None
    except Exception:
        logger.warning("Failed to generate recommend reason", exc_info=True)
        return None


def _get_reason_key(user_id: int, song_id: int) -> str:
    return f"{_ROAM_PREFIX}:{_SUFFIX_REASON}:{user_id}:{song_id}"


async def _store_recommend_reason(user_id: int, song_id: int, reason: str) -> None:
    key = _get_reason_key(user_id, song_id)
    await _rc.redis_client.set(key, reason)
    await _ensure_ttl(key)


async def _load_recommend_reason(user_id: int, song_id: int) -> str | None:
    key = _get_reason_key(user_id, song_id)
    return await _rc.redis_client.get(key)


# ---------------------------------------------------------------------------
# next_song / prev_song / favorite_song / dislike_song 增强版
# ---------------------------------------------------------------------------


async def next_song_with_reason(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """下一首：生成新歌时附带 AI 推荐理由，纯导航时返回 None。"""
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    position = await _read_position(user_id)
    prev_song_title = None

    if position < len(playlist) - 1:
        # 纯导航
        new_position = position + 1
        if position >= 0:
            prev_music = await _load_music_detail(db, playlist[position])
            prev_song_title = prev_music.title if prev_music else None
    else:
        # 生成新歌
        pref, dislike = await _read_pools(user_id)
        exclude_ids = set(playlist)
        if position >= 0:
            prev_music = await _load_music_detail(db, playlist[position])
            prev_song_title = prev_music.title if prev_music else None
        new_music = await _generate_next_song(
            db, user_id, pref, dislike, exclude_ids
        )
        playlist.append(new_music.id)
        playlist_key = _roam_key(user_id, _SUFFIX_PLAYLIST)
        await _rc.redis_client.rpush(playlist_key, str(new_music.id))
        new_position = len(playlist) - 1

        # AI 推荐理由
        current_song_dict = await _music_to_dict(db, user_id, new_music)
        reason = await _generate_recommend_reason(
            current_song_dict, pref, prev_song_title
        )
        if reason:
            await _store_recommend_reason(user_id, new_music.id, reason)

        await _record_action(user_id, f"next:{new_music.id}")

    # 更新位置
    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    await _rc.redis_client.set(position_key, str(new_position))

    # 返回状态
    current_id = playlist[new_position]
    music = await _load_music_detail(db, current_id)
    assert music is not None

    pref, dislike = await _read_pools(user_id)
    loaded_reason = await _load_recommend_reason(user_id, current_id)

    return {
        "playlist": playlist,
        "position": new_position,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
        "recommend_reason": loaded_reason,
    }


async def prev_song_no_reason(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """上一首：纯导航，无推荐理由。"""
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    position = await _read_position(user_id)
    new_position = max(0, position - 1)

    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    await _rc.redis_client.set(position_key, str(new_position))

    current_id = playlist[new_position]
    music = await _load_music_detail(db, current_id)
    assert music is not None

    pref, dislike = await _read_pools(user_id)
    return {
        "playlist": playlist,
        "position": new_position,
        "current_song": await _music_to_dict(db, user_id, music),
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
        "recommend_reason": None,
    }


async def favorite_song_with_action(
    db: AsyncSession,
    user_id: int,
    song_id: int,
    *,
    playlist_id: int | None = None,
) -> dict:
    """收藏 + 记录行为。"""
    result = await favorite_song(db, user_id, song_id, playlist_id=playlist_id)
    await _record_action(user_id, f"fav:{song_id}")
    return result


async def dislike_song_with_action(
    user_id: int,
    song_id: int,
    reasons: dict | None = None,
) -> dict:
    """不喜欢 + 记录行为。"""
    result = await dislike_song(user_id, song_id, reasons)
    await _record_action(user_id, f"dislike:{song_id}")
    return result


# ---------------------------------------------------------------------------
# AI 品味总结
# ---------------------------------------------------------------------------


async def generate_roam_report(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """生成漫游品味总结报告。"""
    playlist = await _read_playlist(user_id)
    actions = await _read_actions(user_id)
    pref, dislike = await _read_pools(user_id)

    favorited_ids = [
        int(a.split(":", 1)[1])
        for a in actions
        if a.startswith("fav:")
    ]
    disliked_ids = [
        int(a.split(":", 1)[1])
        for a in actions
        if a.startswith("dislike:")
    ]

    # 加载收藏歌曲详情
    favorited_songs = []
    for fid in favorited_ids:
        music = await _load_music_detail(db, fid)
        if music:
            favorited_songs.append(await _music_to_dict(db, user_id, music))

    # AI 生成总结
    taste_summary = "今天你探索了新的音乐领域。"
    recommendation = "继续漫游，发现更多惊喜。"

    try:
        client = _deepseek_module.DeepSeekClient(
            model=settings.deepseek_flash_model,
            enable_thinking=False,
        )
        prompt_data = {
            "探索歌曲数": len(playlist),
            "收藏歌曲数": len(favorited_ids),
            "跳过歌曲数": len(disliked_ids),
            "收藏歌曲": [
                f"{s.get('title', '')} - {_format_authors(s)}"
                for s in favorited_songs
            ][:5],
            "偏好趋势": _describe_pool(pref),
            "回避趋势": _describe_pool(dislike),
        }
        response = await client.chat(
            [
                ChatMessage(role="system", content=REPORT_PROMPT),
                ChatMessage(
                    role="user",
                    content=json.dumps(prompt_data, ensure_ascii=False, default=str),
                ),
            ],
            temperature=0.5,
            max_tokens=300,
        )
        raw = (response.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        parsed = json.loads(raw)
        taste_summary = parsed.get("taste_summary", taste_summary)
        recommendation = parsed.get("recommendation")
    except Exception:
        logger.warning("Failed to generate roam report", exc_info=True)

    return {
        "total_songs": len(playlist),
        "favorited_count": len(favorited_ids),
        "disliked_count": len(disliked_ids),
        "favorited_songs": favorited_songs,
        "taste_summary": taste_summary,
        "recommendation": recommendation,
    }


async def end_roam(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """结束漫游 session，生成报告并清除数据。"""
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    report = await generate_roam_report(db, user_id)
    await _clear_roam_session(user_id)
    return report


# ---------------------------------------------------------------------------
# 自然语言引导
# ---------------------------------------------------------------------------


async def guide_roam(
    db: AsyncSession,
    user_id: int,
    hint: str,
) -> dict:
    """解析自然语言引导并调整漫游方向。"""
    playlist = await _read_playlist(user_id)
    if not playlist:
        raise BusinessError(
            "No active roam session",
            code=ErrorCode.MUSIC_NOT_FOUND,
        )

    pref, dislike = await _read_pools(user_id)

    # AI 解析意图
    intent_description = "按你的方向探索中"
    adjustments = {}
    try:
        client = _deepseek_module.DeepSeekClient(
            model=settings.deepseek_flash_model,
            enable_thinking=False,
        )
        response = await client.chat(
            [
                ChatMessage(
                    role="system",
                    content=GUIDE_PROMPT.format(current_pref=_describe_pool(pref)),
                ),
                ChatMessage(role="user", content=hint),
            ],
            temperature=0.3,
            max_tokens=300,
        )
        raw = (response.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        parsed = json.loads(raw)

        intent_description = parsed.get("intent_description", intent_description)

        if parsed.get("counter_preference"):
            # 反向探索：取反当前偏好
            pref_key = _roam_key(user_id, _SUFFIX_PREF)
            current = await _rc.redis_client.hgetall(pref_key)
            for key, val in current.items():
                try:
                    weight = -float(val)
                    await _rc.redis_client.hset(pref_key, key, str(int(weight)))
                except (ValueError, TypeError):
                    pass
            await _ensure_ttl(pref_key)
        else:
            # 应用调整
            for adj in parsed.get("adjustments", []):
                dim = adj.get("dimension", "")
                value = adj.get("value", "")
                weight = adj.get("weight", 3)
                tag_key = f"{dim}:{value}"
                pref_key = _roam_key(user_id, _SUFFIX_PREF)
                await _rc.redis_client.hincrby(pref_key, tag_key, weight)
                await _ensure_ttl(pref_key)
                adjustments[tag_key] = weight
    except Exception:
        logger.warning("Failed to parse roam guide", exc_info=True)

    # 强制生成下一首歌
    new_state = await _force_next_song(db, user_id)

    return {
        "parsed_intent": intent_description,
        "adjustments": adjustments,
        "new_state": new_state,
    }


async def _force_next_song(
    db: AsyncSession,
    user_id: int,
) -> dict:
    """强制生成下一首歌（用于 guide 后立即刷新）。"""
    playlist = await _read_playlist(user_id)
    pref, dislike = await _read_pools(user_id)
    exclude_ids = set(playlist)

    new_music = await _generate_next_song(
        db, user_id, pref, dislike, exclude_ids
    )
    playlist.append(new_music.id)
    playlist_key = _roam_key(user_id, _SUFFIX_PLAYLIST)
    await _rc.redis_client.rpush(playlist_key, str(new_music.id))
    new_position = len(playlist) - 1

    position_key = _roam_key(user_id, _SUFFIX_POSITION)
    await _rc.redis_client.set(position_key, str(new_position))

    # 生成推荐理由
    current_song_dict = await _music_to_dict(db, user_id, new_music)
    reason = await _generate_recommend_reason(current_song_dict, pref, None)
    if reason:
        await _store_recommend_reason(user_id, new_music.id, reason)

    await _record_action(user_id, f"next:{new_music.id}")

    return {
        "playlist": playlist,
        "position": new_position,
        "current_song": current_song_dict,
        "pref_pool_summary": pref,
        "dislike_pool_summary": dislike,
        "recommend_reason": reason,
    }
