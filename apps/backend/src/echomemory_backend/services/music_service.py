"""提供音乐记录的创建、查询、更新及关联关系管理服务。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

import logging
from datetime import date, timedelta

from sqlalchemy import delete, desc, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from echomemory_backend.core.cache.general import (
    CACHE_MISS,
    CHART_HOT_SONGS_PREFIX,
    CHART_NEW_SONGS_PREFIX,
    build_cache_key,
    cache_delete_pattern,
    cache_get,
    cache_set,
)
from echomemory_backend.models.album import AlbumMusic
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import PlaylistMusic
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.utils.common import escape_like
from echomemory_backend.db.pagination import paginate
from echomemory_backend.schemas.music import PaginatedMusicListOut
from echomemory_backend.services.association_helpers import rebuild_tag_association
from echomemory_backend.services.dictionary_reference_service import (
    validate_emotion_tags_exist,
    validate_instruments_exist,
    validate_interest_tags_exist,
)
from echomemory_backend.services.cache_service import (
    invalidate_album_detail,
    invalidate_dashboard_stats,
    invalidate_lyrics,
    invalidate_music_detail,
    invalidate_playlist_detail,
)
from echomemory_backend.services.user_service import get_user_by_id


# 榜单缓存 TTL：30 分钟
_CHART_CACHE_TTL_SECONDS = 30 * 60


def _is_chart_cacheable_query(
    *,
    is_published: bool,
    style_id: int | None,
    language_id: int | None,
    is_vip: bool | None,
    instrument_id: int | None,
    emotion_tag_id: int | None,
    interest_tag_id: int | None,
    release_date_from: date | None,
    release_date_to: date | None,
    q: str | None,
    sort_by: str,
    limit: int,
) -> tuple[bool, str | None]:
    """判断当前查询是否可命中榜单缓存，并返回缓存键。

    仅当无筛选条件、按热度排序、offset 为 0 时认为是首页榜单查询。
    新歌榜判定为 release_date_from 等于当天往前推 30 天。

    Returns:
        (是否可缓存, 缓存键)。不可缓存时缓存键为 None。
    """
    if not is_published:
        return False, None
    if q is not None:
        return False, None
    if (
        style_id is not None
        or language_id is not None
        or is_vip is not None
        or instrument_id is not None
        or emotion_tag_id is not None
        or interest_tag_id is not None
        or release_date_to is not None
    ):
        return False, None
    if sort_by != "hot":
        return False, None

    if release_date_from is None:
        return True, build_cache_key(CHART_HOT_SONGS_PREFIX, limit)

    expected_new_songs_date = date.today() - timedelta(days=30)
    if release_date_from == expected_new_songs_date:
        return True, build_cache_key(CHART_NEW_SONGS_PREFIX, 30, limit)

    return False, None


async def invalidate_chart_caches() -> None:
    """失效所有音乐榜单缓存（热歌榜、新歌榜）。"""
    await cache_delete_pattern(f"{CHART_HOT_SONGS_PREFIX}:*")
    await cache_delete_pattern(f"{CHART_NEW_SONGS_PREFIX}:*")


async def _set_music_authors(db: AsyncSession, music: Music, author_ids: list[int]) -> None:
    """设置音乐的作者关联，覆盖原有作者。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要设置作者的音乐实例。
        author_ids: 作者用户 ID 列表，按顺序关联。

    Returns:
        None。

    Raises:
        BusinessError: 作者不存在或已被删除时抛出，状态码 404。
    """
    await db.execute(
        delete(MusicAuthor).where(MusicAuthor.music_id == music.id)
    )
    for ordinal, author_id in enumerate(author_ids):
        author = await get_user_by_id(db, author_id)
        if author is None or author.is_deleted:
            raise BusinessError(f"Author with id={author_id} not found", code=ErrorCode.ALBUM_AUTHOR_NOT_FOUND)
        db.add(
            MusicAuthor(
                music_id=music.id, author_id=author_id, ordinal=ordinal
            )
        )


async def _set_music_instruments(
    db: AsyncSession, music: Music, instrument_ids: list[int]
) -> None:
    """设置音乐的乐器关联，覆盖原有乐器。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要设置乐器的音乐实例。
        instrument_ids: 乐器 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的乐器 ID 时抛出，状态码 404。
    """
    await rebuild_tag_association(
        db,
        owner_id=music.id,
        owner_fk="music_id",
        tag_ids=instrument_ids,
        assoc_model=MusicInstrument,
        tag_fk="instrument_id",
        validate_fn=validate_instruments_exist,
    )


async def _set_music_emotion_tags(
    db: AsyncSession, music: Music, tag_ids: list[int]
) -> None:
    """设置音乐的情绪标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要设置情绪标签的音乐实例。
        tag_ids: 情绪标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的情绪标签 ID 时抛出，状态码 404。
    """
    await rebuild_tag_association(
        db,
        owner_id=music.id,
        owner_fk="music_id",
        tag_ids=tag_ids,
        assoc_model=MusicEmotionTag,
        tag_fk="emotion_tag_id",
        validate_fn=validate_emotion_tags_exist,
    )


async def _set_music_interest_tags(
    db: AsyncSession, music: Music, tag_ids: list[int]
) -> None:
    """设置音乐的兴趣标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要设置兴趣标签的音乐实例。
        tag_ids: 兴趣标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的兴趣标签 ID 时抛出，状态码 404。
    """
    await rebuild_tag_association(
        db,
        owner_id=music.id,
        owner_fk="music_id",
        tag_ids=tag_ids,
        assoc_model=MusicInterestTag,
        tag_fk="interest_tag_id",
        validate_fn=validate_interest_tags_exist,
    )


async def create_music(
    db: AsyncSession,
    *,
    title: str,
    is_vip: bool = False,
    source: str | None = None,
    style_id: int | None = None,
    language_id: int | None = None,
    release_date: date | None = None,
    author_ids: list[int] | None = None,
    instrument_ids: list[int] | None = None,
    emotion_tag_ids: list[int] | None = None,
    interest_tag_ids: list[int] | None = None,
    file_url: str | None = None,
    lyrics_url: str | None = None,
    cover_icon_url: str | None = None,
    cover_home_url: str | None = None,
    cover_play_url: str | None = None,
) -> Music:
    """创建音乐记录及其关联关系。

    所有文件上传应在调用本函数之前完成，本函数仅接收 OSS URL。

    Raises:
        BusinessError: 作者不存在或数据库约束冲突时抛出。
    """
    if author_ids and any(i <= 0 for i in author_ids):
        raise BusinessError("Invalid author ID", code=ErrorCode.CLIENT_INVALID_AUTHOR_ID)
    if instrument_ids and any(i <= 0 for i in instrument_ids):
        raise BusinessError("Invalid instrument ID", code=ErrorCode.CLIENT_INVALID_INSTRUMENT_ID)
    if emotion_tag_ids and any(i <= 0 for i in emotion_tag_ids):
        raise BusinessError("Invalid emotion tag ID", code=ErrorCode.CLIENT_INVALID_EMOTION_TAG_ID)
    if interest_tag_ids and any(i <= 0 for i in interest_tag_ids):
        raise BusinessError("Invalid interest tag ID", code=ErrorCode.CLIENT_INVALID_INTEREST_TAG_ID)

    music = Music(
        title=title,
        is_vip=is_vip,
        source=source,
        style_id=style_id,
        language_id=language_id,
        release_date=release_date,
        file_url=file_url,
        lyrics_url=lyrics_url,
        cover_icon_url=cover_icon_url,
        cover_home_url=cover_home_url,
        cover_play_url=cover_play_url,
    )
    db.add(music)
    await db.flush()  # 获取 music.id

    if author_ids:
        await _set_music_authors(db, music, author_ids)
    if instrument_ids:
        await _set_music_instruments(db, music, instrument_ids)
    if emotion_tag_ids:
        await _set_music_emotion_tags(db, music, emotion_tag_ids)
    if interest_tag_ids:
        await _set_music_interest_tags(db, music, interest_tag_ids)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Invalid reference in music data: %s", exc, exc_info=True)
        raise BusinessError("Invalid reference in music data", code=ErrorCode.CLIENT_INVALID_REFERENCE_IN_MUSIC)
    await db.refresh(music)
    await invalidate_dashboard_stats()
    return music


async def get_music_by_id(db: AsyncSession, music_id: int) -> Music | None:
    """根据 ID 获取音乐详情，加载所有关联关系。

    Args:
        db: SQLAlchemy 异步 Session。
        music_id: 要查询的音乐主键 ID。

    Returns:
        找到的音乐实例（含关联关系），不存在时返回 None。
    """
    stmt = (
        select(Music)
        .where(Music.id == music_id)
        .options(
            selectinload(Music.style),
            selectinload(Music.language),
            selectinload(Music.authors).selectinload(MusicAuthor.author),
            selectinload(Music.instruments).selectinload(MusicInstrument.instrument),
            selectinload(Music.emotion_tags).selectinload(
                MusicEmotionTag.emotion_tag
            ),
            selectinload(Music.interest_tags).selectinload(
                MusicInterestTag.interest_tag
            ),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_musics(
    db: AsyncSession,
    *,
    style_id: int | None = None,
    language_id: int | None = None,
    is_vip: bool | None = None,
    is_published: bool = True,
    instrument_id: int | None = None,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    q: str | None = None,
    sort_by: str = "created_at",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """分页列出音乐，支持多条件筛选与排序。默认只返回已上架音乐。

    Args:
        db: SQLAlchemy 异步 Session。
        style_id: 按风格 ID 筛选，默认 None 表示不筛选。
        language_id: 按语言 ID 筛选，默认 None 表示不筛选。
        is_vip: 按是否 VIP 筛选，默认 None 表示不筛选。
        is_published: 按是否上架筛选，默认 True 只返回已上架音乐。
        instrument_id: 按乐器 ID 筛选，默认 None 表示不筛选。
        emotion_tag_id: 按情绪标签 ID 筛选，默认 None 表示不筛选。
        interest_tag_id: 按兴趣标签 ID 筛选，默认 None 表示不筛选。
        release_date_from: 发行日期起始（含），默认 None 表示不限制。
        release_date_to: 发行日期截止（含），默认 None 表示不限制。
        q: 标题模糊搜索关键词，默认 None 表示不搜索。
        sort_by: 排序字段，支持 created_at / play_count / hot，默认 created_at。
        limit: 每页返回的最大记录数，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 音乐实例列表, "total": 总记录数}。
    """
    should_cache, cache_key = _is_chart_cacheable_query(
        is_published=is_published,
        style_id=style_id,
        language_id=language_id,
        is_vip=is_vip,
        instrument_id=instrument_id,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        q=q,
        sort_by=sort_by,
        limit=limit,
    )
    if should_cache and offset == 0:
        cached = await cache_get(cache_key)
        if cached is not CACHE_MISS:
            return cached

    where_clause = [Music.is_published == is_published]
    if style_id is not None:
        where_clause.append(Music.style_id == style_id)
    if language_id is not None:
        where_clause.append(Music.language_id == language_id)
    if is_vip is not None:
        where_clause.append(Music.is_vip == is_vip)
    if q:
        where_clause.append(
            Music.title.ilike(f"%{escape_like(q)}%", escape="\\")
        )
    if instrument_id is not None:
        where_clause.append(
            exists().where(
                (MusicInstrument.music_id == Music.id)
                & (MusicInstrument.instrument_id == instrument_id)
            )
        )
    if emotion_tag_id is not None:
        where_clause.append(
            exists().where(
                (MusicEmotionTag.music_id == Music.id)
                & (MusicEmotionTag.emotion_tag_id == emotion_tag_id)
            )
        )
    if interest_tag_id is not None:
        where_clause.append(
            exists().where(
                (MusicInterestTag.music_id == Music.id)
                & (MusicInterestTag.interest_tag_id == interest_tag_id)
            )
        )
    if release_date_from is not None:
        where_clause.append(Music.release_date >= release_date_from)
    if release_date_to is not None:
        where_clause.append(Music.release_date <= release_date_to)

    _SORT_COLUMNS = {
        "created_at": Music.created_at,
        "play_count": Music.play_count,
        "hot": Music.hot,
    }
    sort_column = _SORT_COLUMNS.get(sort_by, Music.created_at)

    stmt = (
        select(Music)
        .where(*where_clause)
        .order_by(desc(sort_column))
        .options(
            selectinload(Music.authors).selectinload(MusicAuthor.author)
        )
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    result = {"items": page.items, "total": page.total}

    if should_cache and offset == 0:
        serialized = PaginatedMusicListOut.model_validate(result).model_dump()
        await cache_set(cache_key, serialized, _CHART_CACHE_TTL_SECONDS)

    return result


async def search_musics(
    db: AsyncSession,
    *,
    q: str | None = None,
    is_published: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """按标题模糊搜索音乐。

    Args:
        db: SQLAlchemy 异步 Session。
        q: 搜索关键词，默认 None 表示不搜索。
        is_published: 按是否上架筛选，默认 True 只返回已上架音乐。
        limit: 每页返回的最大记录数，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 音乐实例列表, "total": 总记录数}。
    """
    where_clause = [Music.is_published == is_published]
    if q:
        where_clause.append(
            Music.title.ilike(f"%{escape_like(q)}%", escape="\\")
        )

    stmt = (
        select(Music)
        .where(*where_clause)
        .order_by(desc(Music.hot))
        .options(selectinload(Music.authors).selectinload(MusicAuthor.author))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def admin_search_musics(
    db: AsyncSession,
    *,
    q: str | None = None,
    style_id: int | None = None,
    language_id: int | None = None,
    is_vip: bool | None = None,
    is_published: bool | None = None,
    instrument_id: int | None = None,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    sort_by: str = "id",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """管理员查询所有音乐（含未上架），支持搜索、多条件筛选与排序。

    Args:
        db: SQLAlchemy 异步 Session。
        q: 搜索关键词，默认 None 表示不搜索。
        style_id: 按风格 ID 筛选，默认 None 表示不筛选。
        language_id: 按语言 ID 筛选，默认 None 表示不筛选。
        is_vip: 按是否 VIP 筛选，默认 None 表示不筛选。
        is_published: 按是否上架筛选，默认 None 表示不筛选。
        instrument_id: 按乐器 ID 筛选，默认 None 表示不筛选。
        emotion_tag_id: 按情感标签 ID 筛选，默认 None 表示不筛选。
        interest_tag_id: 按兴趣标签 ID 筛选，默认 None 表示不筛选。
        sort_by: 排序字段，支持 id / hot / play_count / created_at，默认 id。
        limit: 每页返回的最大记录数，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 音乐实例列表, "total": 总记录数}。
    """
    where_clause: list = []
    if is_published is not None:
        where_clause.append(Music.is_published == is_published)
    if q:
        where_clause.append(
            Music.title.ilike(f"%{escape_like(q)}%", escape="\\")
        )
    if style_id is not None:
        where_clause.append(Music.style_id == style_id)
    if language_id is not None:
        where_clause.append(Music.language_id == language_id)
    if is_vip is not None:
        where_clause.append(Music.is_vip == is_vip)
    if instrument_id is not None:
        where_clause.append(
            exists().where(
                (MusicInstrument.music_id == Music.id)
                & (MusicInstrument.instrument_id == instrument_id)
            )
        )
    if emotion_tag_id is not None:
        where_clause.append(
            exists().where(
                (MusicEmotionTag.music_id == Music.id)
                & (MusicEmotionTag.emotion_tag_id == emotion_tag_id)
            )
        )
    if interest_tag_id is not None:
        where_clause.append(
            exists().where(
                (MusicInterestTag.music_id == Music.id)
                & (MusicInterestTag.interest_tag_id == interest_tag_id)
            )
        )

    _ADMIN_SORT_COLUMNS = {
        "id": Music.id,
        "hot": Music.hot,
        "play_count": Music.play_count,
        "created_at": Music.created_at,
    }
    sort_column = _ADMIN_SORT_COLUMNS.get(sort_by, Music.id)
    stmt = select(Music).order_by(desc(sort_column)).limit(limit).offset(offset)
    count_stmt = select(func.count()).select_from(Music)

    if where_clause:
        stmt = stmt.where(*where_clause)
        count_stmt = count_stmt.where(*where_clause)

    stmt = stmt.options(
        selectinload(Music.authors).selectinload(MusicAuthor.author),
        selectinload(Music.style),
        selectinload(Music.language),
        selectinload(Music.emotion_tags).selectinload(MusicEmotionTag.emotion_tag),
        selectinload(Music.interest_tags).selectinload(MusicInterestTag.interest_tag),
        selectinload(Music.album_musics).selectinload(AlbumMusic.album),
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()
    return {"items": items, "total": total}


async def update_music(
    db: AsyncSession,
    music: Music,
    *,
    title: str | None = None,
    is_vip: bool | None = None,
    source: str | None = None,
    style_id: int | None = None,
    language_id: int | None = None,
    release_date: date | None = None,
    author_ids: list[int] | None = None,
    instrument_ids: list[int] | None = None,
    emotion_tag_ids: list[int] | None = None,
    interest_tag_ids: list[int] | None = None,
    file_url: str | None = None,
    lyrics_url: str | None = None,
    cover_icon_url: str | None = None,
    cover_home_url: str | None = None,
    cover_play_url: str | None = None,
) -> Music:
    """更新音乐信息及关联关系（含可选文件 URL 替换）。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要更新的音乐实例。
        title: 新标题，默认 None 表示不修改。
        is_vip: 新的 VIP 状态，默认 None 表示不修改。
        source: 新的来源信息，默认 None 表示不修改。
        style_id: 新的风格 ID，默认 None 表示不修改。
        language_id: 新的语言 ID，默认 None 表示不修改。
        release_date: 新的发行日期，默认 None 表示不修改。
        author_ids: 新的作者 ID 列表，默认 None 表示不修改。
        instrument_ids: 新的乐器 ID 列表，默认 None 表示不修改。
        emotion_tag_ids: 新的情绪标签 ID 列表，默认 None 表示不修改。
        interest_tag_ids: 新的兴趣标签 ID 列表，默认 None 表示不修改。
        file_url: 新的音频 URL，默认 None 表示不修改。
        lyrics_url: 新的歌词 URL，默认 None 表示不修改。
        cover_icon_url: 新的封面图标 URL，默认 None 表示不修改。
        cover_home_url: 新的封面 Home URL，默认 None 表示不修改。
        cover_play_url: 新的封面 Play URL，默认 None 表示不修改。

    Returns:
        更新后的音乐实例。

    Raises:
        BusinessError: 作者不存在、关联标签/乐器不存在或数据库约束冲突时抛出。
    """
    if title is not None:
        music.title = title
    if is_vip is not None:
        music.is_vip = is_vip
    if source is not None:
        music.source = source
    if style_id is not None:
        music.style_id = style_id
    if language_id is not None:
        music.language_id = language_id
    if release_date is not None:
        music.release_date = release_date
    if file_url is not None:
        music.file_url = file_url
    if lyrics_url is not None and lyrics_url != music.lyrics_url:
        music.lyrics_url = lyrics_url
        await invalidate_lyrics(music.id)
    if cover_icon_url is not None:
        music.cover_icon_url = cover_icon_url
    if cover_home_url is not None:
        music.cover_home_url = cover_home_url
    if cover_play_url is not None:
        music.cover_play_url = cover_play_url

    if author_ids is not None:
        await _set_music_authors(db, music, author_ids)
    if instrument_ids is not None:
        await _set_music_instruments(db, music, instrument_ids)

    tag_changed = False
    if emotion_tag_ids is not None:
        await _set_music_emotion_tags(db, music, emotion_tag_ids)
        tag_changed = True
    if interest_tag_ids is not None:
        await _set_music_interest_tags(db, music, interest_tag_ids)
        tag_changed = True

    if tag_changed:
        # 先 flush 音乐标签变更，确保同步查询能看到最新状态
        await db.flush()

        # 局部导入避免循环依赖
        from echomemory_backend.services.album_service import (
            _sync_album_tags_from_musics,
        )
        from echomemory_backend.services.playlist_service import (
            _sync_playlist_tags_from_musics,
        )

        # 同步所属专辑标签
        stmt = select(AlbumMusic.album_id).where(AlbumMusic.music_id == music.id)
        result = await db.execute(stmt)
        album_id = result.scalar_one_or_none()
        if album_id is not None:
            await _sync_album_tags_from_musics(db, album_id)
            await invalidate_album_detail(album_id)

        # 同步所属歌单标签
        stmt = select(PlaylistMusic.playlist_id).where(
            PlaylistMusic.music_id == music.id
        )
        result = await db.execute(stmt)
        for pl_id in result.scalars().all():
            await _sync_playlist_tags_from_musics(db, pl_id)
            await invalidate_playlist_detail(pl_id)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Invalid reference in music data: %s", exc, exc_info=True)
        raise BusinessError("Invalid reference in music data", code=ErrorCode.CLIENT_INVALID_REFERENCE_IN_MUSIC)
    await db.refresh(music)
    await invalidate_chart_caches()
    await invalidate_music_detail(music.id)
    return music


async def set_music_published(db: AsyncSession, music: Music, published: bool) -> Music:
    """设置音乐上架/下架状态。

    Args:
        db: SQLAlchemy 异步 Session。
        music: 要设置状态的音乐实例。
        published: True 表示上架，False 表示下架。

    Returns:
        更新后的音乐实例。
    """
    music.is_published = published
    await db.commit()
    await db.refresh(music)
    await invalidate_chart_caches()
    await invalidate_music_detail(music.id)
    await invalidate_dashboard_stats()
    return music
