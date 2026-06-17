"""推荐系统业务服务模块。

提供基于用户画像标签的轻量随机推荐：每日推荐、私人雷达、推荐歌单、
推荐专辑以及推荐榜聚合。不涉及热度排序与 AI 算法。
"""

import logging
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.album import (
    Album,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
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
from echomemory_backend.models.user_tag import (
    UserEmotionTag,
    UserInterestTag,
    UserLanguage,
    UserStyle,
)
from echomemory_backend.db.pagination import paginate
from echomemory_backend.services.collection_service import (
    get_collected_music_ids,
)

logger = logging.getLogger(__name__)

_DAILY_RECOMMENDATION_SIZE = 10
_RADAR_TOTAL_SIZE = 20
_RADAR_COLLECTED_SIZE = 10


def _today() -> date:
    """获取当前 UTC 日期。

    Returns:
        当前 UTC 日期。
    """
    return datetime.now(timezone.utc).date()


def _seconds_until_next_utc_hour(target_hour: int) -> float:
    """计算当前时间到下一个 UTC 指定整点的秒数。

    Args:
        target_hour: 目标小时（0-23）。

    Returns:
        距离下一个目标整点的秒数。
    """
    now = datetime.now(timezone.utc)
    target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if target < now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


async def _get_user_tag_ids(
    db: AsyncSession, user_id: int
) -> dict[str, list[int]]:
    """查询用户的四类偏好标签 ID。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        包含 emotion、interest、style、language 四个键的字典，值为标签 ID 列表。
    """
    emotion_stmt = select(UserEmotionTag.emotion_tag_id).where(
        UserEmotionTag.user_id == user_id
    )
    interest_stmt = select(UserInterestTag.interest_tag_id).where(
        UserInterestTag.user_id == user_id
    )
    style_stmt = select(UserStyle.style_id).where(UserStyle.user_id == user_id)
    language_stmt = select(UserLanguage.language_id).where(
        UserLanguage.user_id == user_id
    )

    return {
        "emotion": list((await db.execute(emotion_stmt)).scalars().all()),
        "interest": list((await db.execute(interest_stmt)).scalars().all()),
        "style": list((await db.execute(style_stmt)).scalars().all()),
        "language": list((await db.execute(language_stmt)).scalars().all()),
    }


async def _random_music_ids(
    db: AsyncSession,
    *,
    extra_conditions: list | None = None,
    exclude_ids: set[int] | None = None,
    limit: int,
) -> list[int]:
    """从已上架音乐中随机抽取指定数量的音乐 ID。

    Args:
        db: SQLAlchemy 异步 Session。
        extra_conditions: 额外的筛选条件列表，默认无。
        exclude_ids: 需要排除的音乐 ID 集合，默认不排除。
        limit: 抽取数量上限。

    Returns:
        随机抽选的音乐 ID 列表。
    """
    where_clause = [Music.is_published.is_(True)]
    if extra_conditions:
        where_clause.extend(extra_conditions)
    if exclude_ids:
        where_clause.append(Music.id.not_in(list(exclude_ids)))

    stmt = (
        select(Music.id)
        .where(*where_clause)
        .order_by(func.random())
        .limit(limit)
    )
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def _all_collected_music_ids(
    db: AsyncSession,
    user_id: int,
) -> set[int]:
    """查询用户全部已收藏音乐 ID（含未上架）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        用户已收藏音乐 ID 集合。
    """
    stmt = (
        select(PlaylistMusic.music_id)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(Playlist.user_id == user_id)
        .distinct()
    )
    rows = await db.execute(stmt)
    return set(rows.scalars().all())


async def _random_collected_music_ids(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int,
) -> list[int]:
    """从用户已上架收藏音乐中随机抽取指定数量的音乐 ID。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 抽取数量上限。

    Returns:
        随机抽选的已收藏音乐 ID 列表。
    """
    subq = (
        select(PlaylistMusic.music_id)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .join(Music, PlaylistMusic.music_id == Music.id)
        .where(
            Playlist.user_id == user_id,
            Music.is_published.is_(True),
        )
        .distinct()
        .subquery()
    )
    stmt = select(subq.c.music_id).order_by(func.random()).limit(limit)
    rows = await db.execute(stmt)
    return list(rows.scalars().all())


async def generate_daily_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    target_date: date | None = None,
) -> list[int]:
    """为用户生成指定日期的每日推荐音乐 ID 列表。

    分配策略：情绪 2 + 兴趣 2 + 风格 2 + 语言 2 + 兜底 2，共 10 首。
    任意维度候选不足时，由兜底池补齐；全库不足 10 首则返回全部。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        target_date: 目标日期，默认当前 UTC 日期（仅用于保存，生成逻辑不依赖日期）。

    Returns:
        去重后的音乐 ID 列表，长度不超过 10。
    """
    if target_date is None:
        target_date = _today()

    tags = await _get_user_tag_ids(db, user_id)
    selected: set[int] = set()
    per_dimension = 2

    # 情绪标签
    if tags["emotion"]:
        emotion_ids = await _random_music_ids(
            db,
            extra_conditions=[
                exists().where(
                    (MusicEmotionTag.music_id == Music.id)
                    & (MusicEmotionTag.emotion_tag_id.in_(tags["emotion"]))
                )
            ],
            exclude_ids=selected,
            limit=per_dimension,
        )
        selected.update(emotion_ids)

    # 兴趣标签
    if tags["interest"] and len(selected) < _DAILY_RECOMMENDATION_SIZE:
        interest_ids = await _random_music_ids(
            db,
            extra_conditions=[
                exists().where(
                    (MusicInterestTag.music_id == Music.id)
                    & (MusicInterestTag.interest_tag_id.in_(tags["interest"]))
                )
            ],
            exclude_ids=selected,
            limit=per_dimension,
        )
        selected.update(interest_ids)

    # 风格标签
    if tags["style"] and len(selected) < _DAILY_RECOMMENDATION_SIZE:
        style_ids = await _random_music_ids(
            db,
            extra_conditions=[Music.style_id.in_(tags["style"])],
            exclude_ids=selected,
            limit=per_dimension,
        )
        selected.update(style_ids)

    # 语言标签
    if tags["language"] and len(selected) < _DAILY_RECOMMENDATION_SIZE:
        language_ids = await _random_music_ids(
            db,
            extra_conditions=[Music.language_id.in_(tags["language"])],
            exclude_ids=selected,
            limit=per_dimension,
        )
        selected.update(language_ids)

    # 兜底：从全部已上架音乐中补齐
    if len(selected) < _DAILY_RECOMMENDATION_SIZE:
        fallback_ids = await _random_music_ids(
            db,
            exclude_ids=selected,
            limit=_DAILY_RECOMMENDATION_SIZE - len(selected),
        )
        selected.update(fallback_ids)

    return list(selected)[:_DAILY_RECOMMENDATION_SIZE]


async def get_or_generate_daily_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    target_date: date | None = None,
) -> list[int]:
    """获取用户指定日期的每日推荐，不存在则生成并持久化。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        target_date: 目标日期，默认当前 UTC 日期。

    Returns:
        当日每日推荐音乐 ID 列表。
    """
    if target_date is None:
        target_date = _today()

    stmt = select(UserDailyRecommendation).where(
        UserDailyRecommendation.user_id == user_id,
        UserDailyRecommendation.date == target_date,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return list(existing.music_ids)

    music_ids = await generate_daily_recommendations(db, user_id, target_date=target_date)
    db.add(
        UserDailyRecommendation(
            user_id=user_id,
            date=target_date,
            music_ids=music_ids,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(stmt)).scalar_one()
        return list(existing.music_ids)
    return music_ids


async def generate_radar_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    target_date: date | None = None,
) -> list[int]:
    """为用户生成指定日期的私人雷达音乐 ID 列表。

    策略：
    1. 从已收藏音乐随机抽最多 10 首；
    2. 若不足 10 首，剩余名额转入推荐部分；
    3. 从用户的情绪/兴趣/风格/语言标签中各随机抽 1 个，构建未收藏候选池；
    4. 候选不足时用全库未收藏已上架音乐兜底；
    5. 合并后去重，返回最多 20 首。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        target_date: 目标日期，默认当前 UTC 日期。

    Returns:
        去重后的音乐 ID 列表，长度不超过 20。
    """
    if target_date is None:
        target_date = _today()

    all_collected_ids = await _all_collected_music_ids(db, user_id)
    collected_ids = await _random_collected_music_ids(
        db, user_id, limit=_RADAR_COLLECTED_SIZE
    )
    collected_set = set(collected_ids)
    need = _RADAR_TOTAL_SIZE - len(collected_set)

    recommended: set[int] = set()
    if need > 0:
        tags = await _get_user_tag_ids(db, user_id)
        chosen_conditions = []
        if tags["emotion"]:
            tag_id = random.choice(tags["emotion"])
            chosen_conditions.append(
                exists().where(
                    (MusicEmotionTag.music_id == Music.id)
                    & (MusicEmotionTag.emotion_tag_id == tag_id)
                )
            )
        if tags["interest"]:
            tag_id = random.choice(tags["interest"])
            chosen_conditions.append(
                exists().where(
                    (MusicInterestTag.music_id == Music.id)
                    & (MusicInterestTag.interest_tag_id == tag_id)
                )
            )
        if tags["style"]:
            tag_id = random.choice(tags["style"])
            chosen_conditions.append(Music.style_id == tag_id)
        if tags["language"]:
            tag_id = random.choice(tags["language"])
            chosen_conditions.append(Music.language_id == tag_id)

        exclude = all_collected_ids | recommended
        if chosen_conditions:
            tag_based_ids = await _random_music_ids(
                db,
                extra_conditions=[or_(*chosen_conditions)],
                exclude_ids=exclude,
                limit=need,
            )
            recommended.update(tag_based_ids)

        # 兜底补齐
        if len(recommended) < need:
            exclude = all_collected_ids | recommended
            fallback_ids = await _random_music_ids(
                db,
                exclude_ids=exclude,
                limit=need - len(recommended),
            )
            recommended.update(fallback_ids)

    result_ids = collected_ids + list(recommended)
    return result_ids[:_RADAR_TOTAL_SIZE]


async def get_or_generate_radar_recommendations(
    db: AsyncSession,
    user_id: int,
    *,
    target_date: date | None = None,
) -> list[int]:
    """获取用户指定日期的私人雷达，不存在则生成并持久化。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        target_date: 目标日期，默认当前 UTC 日期。

    Returns:
        当日私人雷达音乐 ID 列表。
    """
    if target_date is None:
        target_date = _today()

    stmt = select(UserRadarRecommendation).where(
        UserRadarRecommendation.user_id == user_id,
        UserRadarRecommendation.date == target_date,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return list(existing.music_ids)

    music_ids = await generate_radar_recommendations(db, user_id, target_date=target_date)
    db.add(
        UserRadarRecommendation(
            user_id=user_id,
            date=target_date,
            music_ids=music_ids,
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = (await db.execute(stmt)).scalar_one()
        return list(existing.music_ids)
    return music_ids


async def _load_musics_with_authors(
    db: AsyncSession, music_ids: list[int]
) -> list[Music]:
    """按传入顺序加载音乐列表，并预加载作者信息。

    Args:
        db: SQLAlchemy 异步 Session。
        music_ids: 音乐主键列表。

    Returns:
        按 music_ids 顺序排列的音乐实例列表；不存在的 ID 会被跳过。
    """
    if not music_ids:
        return []
    from echomemory_backend.models.music import MusicAuthor

    stmt = (
        select(Music)
        .where(Music.id.in_(music_ids))
        .options(
            selectinload(Music.authors).selectinload(MusicAuthor.author),
            selectinload(Music.album_musics).selectinload(AlbumMusic.album),
        )
    )
    rows = await db.execute(stmt)
    music_map = {m.id: m for m in rows.scalars().all()}
    return [music_map[mid] for mid in music_ids if mid in music_map]


async def get_daily_recommendation_musics(
    db: AsyncSession, user_id: int
) -> list[Music]:
    """获取用户当日每日推荐的音乐对象列表（含作者）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按推荐顺序排列的音乐实例列表。
    """
    music_ids = await get_or_generate_daily_recommendations(db, user_id)
    return await _load_musics_with_authors(db, music_ids)


async def get_radar_recommendation_musics(
    db: AsyncSession, user_id: int
) -> list[Music]:
    """获取用户当日私人雷达的音乐对象列表（含作者）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        按推荐顺序排列的音乐实例列表。
    """
    music_ids = await get_or_generate_radar_recommendations(db, user_id)
    return await _load_musics_with_authors(db, music_ids)


def _tag_match_for_playlists(user_tag_ids: dict[str, list[int]]) -> list:
    """构建歌单标签匹配条件。

    Args:
        user_tag_ids: 用户四类标签 ID 字典。

    Returns:
        用于 SQL where 的标签匹配条件列表；无情绪/兴趣标签时返回空列表。
    """
    conditions = []
    emotion_ids = user_tag_ids.get("emotion", [])
    interest_ids = user_tag_ids.get("interest", [])
    if emotion_ids:
        conditions.append(
            exists().where(
                (PlaylistEmotionTag.playlist_id == Playlist.id)
                & (PlaylistEmotionTag.emotion_tag_id.in_(emotion_ids))
            )
        )
    if interest_ids:
        conditions.append(
            exists().where(
                (PlaylistInterestTag.playlist_id == Playlist.id)
                & (PlaylistInterestTag.interest_tag_id.in_(interest_ids))
            )
        )
    return conditions


def _tag_match_for_albums(user_tag_ids: dict[str, list[int]]) -> list:
    """构建专辑标签匹配条件。

    Args:
        user_tag_ids: 用户四类标签 ID 字典。

    Returns:
        用于 SQL where 的标签匹配条件列表；无情绪/兴趣标签时返回空列表。
    """
    conditions = []
    emotion_ids = user_tag_ids.get("emotion", [])
    interest_ids = user_tag_ids.get("interest", [])
    if emotion_ids:
        conditions.append(
            exists().where(
                (AlbumEmotionTag.album_id == Album.id)
                & (AlbumEmotionTag.emotion_tag_id.in_(emotion_ids))
            )
        )
    if interest_ids:
        conditions.append(
            exists().where(
                (AlbumInterestTag.album_id == Album.id)
                & (AlbumInterestTag.interest_tag_id.in_(interest_ids))
            )
        )
    return conditions


def _playlist_order_by() -> list:
    """歌单推荐排序：热度倒序，ID 倒序作为稳定 tie-breaker。"""
    return [Playlist.hot.desc(), Playlist.id.desc()]


async def recommend_playlists(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """根据用户口味推荐公开歌单。

    优先推荐情绪/兴趣标签有交集的非空公开歌单；不足时按热度兜底。
    排除用户自己的歌单、私密歌单和系统喜欢歌单。
    若第一页仍为空，则放宽为所有公开非空歌单（含自己的公开歌单）按热度补齐。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 每页数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 歌单实例列表, "total": 总记录数}。
    """
    base_where = [
        Playlist.is_private.is_(False),
        Playlist.is_like.is_(False),
        Playlist.user_id != user_id,
        exists().where(PlaylistMusic.playlist_id == Playlist.id),
    ]

    tags = await _get_user_tag_ids(db, user_id)
    tag_conditions = _tag_match_for_playlists(tags)

    result: dict[str, object]
    if tag_conditions:
        tag_where = base_where + [or_(*tag_conditions)]
        stmt = (
            select(Playlist)
            .where(*tag_where)
            .order_by(*_playlist_order_by())
            .options(selectinload(Playlist.user))
        )
        tag_page = await paginate(
            db, stmt, tag_where, limit=limit, offset=offset
        )
        if len(tag_page.items) == limit or (
            offset == 0 and tag_page.total >= limit
        ):
            result = {"items": tag_page.items, "total": tag_page.total}
        else:
            # 标签匹配不足，用兜底补齐当前页
            fallback_where = base_where + [
                ~or_(*tag_conditions) if len(tag_conditions) > 1 else ~tag_conditions[0]
            ]
            fallback_stmt = (
                select(Playlist)
                .where(*fallback_where)
                .order_by(*_playlist_order_by())
                .options(selectinload(Playlist.user))
            )
            fallback_limit = limit - len(tag_page.items)
            fallback_offset = max(0, offset - tag_page.total)
            fallback_page = await paginate(
                db, fallback_stmt, fallback_where, limit=fallback_limit, offset=fallback_offset
            )
            result = {
                "items": tag_page.items + fallback_page.items,
                "total": tag_page.total + fallback_page.total,
            }
    else:
        # 无标签：按热度兜底
        stmt = (
            select(Playlist)
            .where(*base_where)
            .order_by(*_playlist_order_by())
            .options(selectinload(Playlist.user))
        )
        page = await paginate(db, stmt, base_where, limit=limit, offset=offset)
        result = {"items": page.items, "total": page.total}

    # 第一页仍为空时，放宽“排除自己”的限制，用所有公开非空歌单按热度补齐
    if offset == 0 and not result["items"]:
        broaden_where = [
            Playlist.is_private.is_(False),
            Playlist.is_like.is_(False),
            exists().where(PlaylistMusic.playlist_id == Playlist.id),
        ]
        broaden_stmt = (
            select(Playlist)
            .where(*broaden_where)
            .order_by(*_playlist_order_by())
            .options(selectinload(Playlist.user))
        )
        broaden_page = await paginate(
            db, broaden_stmt, broaden_where, limit=limit, offset=0
        )
        result = {"items": broaden_page.items, "total": broaden_page.total}

    return result


def _album_order_by() -> list:
    """专辑推荐排序：热度倒序，ID 倒序作为稳定 tie-breaker。"""
    return [Album.hot.desc(), Album.id.desc()]


async def recommend_albums(
    db: AsyncSession,
    user_id: int,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """根据用户口味推荐专辑。

    优先推荐情绪/兴趣标签有交集的未删除非空专辑；不足时按热度兜底。
    若第一页仍为空，则放宽“非空专辑”的限制，用所有未删除专辑按热度补齐。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 每页数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 专辑实例列表, "total": 总记录数}。
    """
    base_where = [
        Album.is_deleted.is_(False),
        exists().where(AlbumMusic.album_id == Album.id),
    ]

    tags = await _get_user_tag_ids(db, user_id)
    tag_conditions = _tag_match_for_albums(tags)

    result: dict[str, object]
    if tag_conditions:
        tag_where = base_where + [or_(*tag_conditions)]
        stmt = select(Album).where(*tag_where).order_by(*_album_order_by())
        tag_page = await paginate(
            db, stmt, tag_where, limit=limit, offset=offset
        )
        if len(tag_page.items) == limit or (
            offset == 0 and tag_page.total >= limit
        ):
            result = {"items": tag_page.items, "total": tag_page.total}
        else:
            fallback_where = base_where + [
                ~or_(*tag_conditions) if len(tag_conditions) > 1 else ~tag_conditions[0]
            ]
            fallback_stmt = select(Album).where(*fallback_where).order_by(
                *_album_order_by()
            )
            fallback_limit = limit - len(tag_page.items)
            fallback_offset = max(0, offset - tag_page.total)
            fallback_page = await paginate(
                db, fallback_stmt, fallback_where, limit=fallback_limit, offset=fallback_offset
            )
            result = {
                "items": tag_page.items + fallback_page.items,
                "total": tag_page.total + fallback_page.total,
            }
    else:
        stmt = select(Album).where(*base_where).order_by(*_album_order_by())
        page = await paginate(db, stmt, base_where, limit=limit, offset=offset)
        result = {"items": page.items, "total": page.total}

    # 第一页仍为空时，放宽“非空专辑”限制，用所有未删除专辑按热度补齐
    if offset == 0 and not result["items"]:
        broaden_where = [Album.is_deleted.is_(False)]
        broaden_stmt = select(Album).where(*broaden_where).order_by(
            *_album_order_by()
        )
        broaden_page = await paginate(
            db, broaden_stmt, broaden_where, limit=limit, offset=0
        )
        result = {"items": broaden_page.items, "total": broaden_page.total}

    return result


async def get_recommendation_chart(
    db: AsyncSession,
    *,
    target_date: date | None = None,
    limit: int = 20,
) -> list[tuple[Music, int]]:
    """获取指定日期的推荐榜。

    统计当天每首音乐被多少个用户的每日推荐收录，按用户数倒序排列。

    Args:
        db: SQLAlchemy 异步 Session。
        target_date: 目标日期，默认当前 UTC 日期。
        limit: 返回数量上限，默认 20。

    Returns:
        由 (音乐实例, 被推荐用户数) 组成的列表。
    """
    if target_date is None:
        target_date = _today()

    unnest_subq = (
        select(
            UserDailyRecommendation.user_id,
            func.unnest(UserDailyRecommendation.music_ids).label("music_id"),
        )
        .where(UserDailyRecommendation.date == target_date)
        .subquery()
    )

    from echomemory_backend.models.music import MusicAuthor

    stmt = (
        select(
            Music,
            func.count(unnest_subq.c.user_id.distinct()).label("recommend_count"),
        )
        .join(unnest_subq, Music.id == unnest_subq.c.music_id)
        .where(Music.is_published.is_(True))
        .group_by(Music.id)
        .order_by(desc("recommend_count"), desc(Music.id))
        .options(selectinload(Music.authors).selectinload(MusicAuthor.author))
        .limit(limit)
    )
    rows = await db.execute(stmt)
    return [(row.Music, row.recommend_count) for row in rows.all()]


async def refresh_all_daily_and_radar_recommendations(
    db: AsyncSession,
    *,
    target_date: date | None = None,
    batch_size: int = 100,
) -> dict[str, int]:
    """为所有活跃用户批量生成指定日期的每日推荐与私人雷达。

    Args:
        db: SQLAlchemy 异步 Session。
        target_date: 目标日期，默认当前 UTC 日期。
        batch_size: 每批处理用户数，默认 100。

    Returns:
        {"daily": N, "radar": M} 统计字典。
    """
    if target_date is None:
        target_date = _today()

    from echomemory_backend.models.user import User

    user_ids_stmt = (
        select(User.id)
        .where(User.is_deleted.is_(False), User.status == 0)
        .order_by(User.id)
    )
    user_ids = list((await db.execute(user_ids_stmt)).scalars().all())

    daily_count = 0
    radar_count = 0
    for i in range(0, len(user_ids), batch_size):
        batch = user_ids[i : i + batch_size]
        for uid in batch:
            await get_or_generate_daily_recommendations(
                db, uid, target_date=target_date
            )
            daily_count += 1
            await get_or_generate_radar_recommendations(
                db, uid, target_date=target_date
            )
            radar_count += 1
        await db.commit()
        if i + batch_size < len(user_ids):
            import asyncio

            await asyncio.sleep(0.1)

    logger.info(
        "Recommendations refreshed: daily=%d, radar=%d, date=%s",
        daily_count,
        radar_count,
        target_date.isoformat(),
    )
    return {"daily": daily_count, "radar": radar_count}
