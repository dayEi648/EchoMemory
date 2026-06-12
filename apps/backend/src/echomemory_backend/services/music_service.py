"""提供音乐记录的创建、查询、更新及关联关系管理服务。"""

import logging
from datetime import date

from sqlalchemy import delete, desc, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from echomemory_backend.models.album import AlbumMusic
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.playlist import PlaylistMusic
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.services.dictionary_reference_service import (
    validate_emotion_tags_exist,
    validate_instruments_exist,
    validate_interest_tags_exist,
)
from echomemory_backend.services.user_service import get_user_by_id


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
            raise BusinessError(f"Author with id={author_id} not found", 404)
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
    await validate_instruments_exist(db, instrument_ids)
    await db.execute(
        delete(MusicInstrument).where(MusicInstrument.music_id == music.id)
    )
    for instrument_id in instrument_ids:
        db.add(
            MusicInstrument(music_id=music.id, instrument_id=instrument_id)
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
    await validate_emotion_tags_exist(db, tag_ids)
    await db.execute(
        delete(MusicEmotionTag).where(MusicEmotionTag.music_id == music.id)
    )
    for tag_id in tag_ids:
        db.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=tag_id))


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
    await validate_interest_tags_exist(db, tag_ids)
    await db.execute(
        delete(MusicInterestTag).where(MusicInterestTag.music_id == music.id)
    )
    for tag_id in tag_ids:
        db.add(MusicInterestTag(music_id=music.id, interest_tag_id=tag_id))


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
        raise BusinessError("Invalid author ID", 400)
    if instrument_ids and any(i <= 0 for i in instrument_ids):
        raise BusinessError("Invalid instrument ID", 400)
    if emotion_tag_ids and any(i <= 0 for i in emotion_tag_ids):
        raise BusinessError("Invalid emotion tag ID", 400)
    if interest_tag_ids and any(i <= 0 for i in interest_tag_ids):
        raise BusinessError("Invalid interest tag ID", 400)

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
        raise BusinessError("Invalid reference in music data", 400)
    await db.refresh(music)
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
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """分页列出音乐，支持多条件筛选。默认只返回已上架音乐。

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
        limit: 每页返回的最大记录数，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 音乐实例列表, "total": 总记录数}。
    """
    where_clause = [Music.is_published == is_published]
    if style_id is not None:
        where_clause.append(Music.style_id == style_id)
    if language_id is not None:
        where_clause.append(Music.language_id == language_id)
    if is_vip is not None:
        where_clause.append(Music.is_vip == is_vip)
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        where_clause.append(Music.title.ilike(f"%{escaped_q}%", escape="\\"))
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

    stmt = (
        select(Music)
        .where(*where_clause)
        .order_by(desc(Music.created_at))
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(Music.authors).selectinload(MusicAuthor.author)
        )
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


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
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        where_clause.append(Music.title.ilike(f"%{escaped_q}%", escape="\\"))

    stmt = (
        select(Music)
        .where(*where_clause)
        .order_by(desc(Music.hot))
        .limit(limit)
        .offset(offset)
        .options(selectinload(Music.authors).selectinload(MusicAuthor.author))
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


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
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """管理员查询所有音乐（含未上架），支持搜索和多条件筛选。

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
        limit: 每页返回的最大记录数，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        {"items": 音乐实例列表, "total": 总记录数}。
    """
    where_clause: list = []
    if is_published is not None:
        where_clause.append(Music.is_published == is_published)
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        where_clause.append(Music.title.ilike(f"%{escaped_q}%", escape="\\"))
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

    stmt = select(Music).order_by(Music.id).limit(limit).offset(offset)
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
    if lyrics_url is not None:
        music.lyrics_url = lyrics_url
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

        # 同步所属歌单标签
        stmt = select(PlaylistMusic.playlist_id).where(
            PlaylistMusic.music_id == music.id
        )
        result = await db.execute(stmt)
        for pl_id in result.scalars().all():
            await _sync_playlist_tags_from_musics(db, pl_id)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Invalid reference in music data: %s", exc, exc_info=True)
        raise BusinessError("Invalid reference in music data", 400)
    await db.refresh(music)
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
    return music
