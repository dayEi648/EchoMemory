from datetime import date

from sqlalchemy import delete, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.dictionary import EmotionTag, Instrument, InterestTag
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.user import User
from echomemory_backend.services.user_service import BusinessError, get_user_by_id


async def _set_music_authors(db: AsyncSession, music: Music, author_ids: list[int]) -> None:
    """设置音乐的作者关联，覆盖原有作者。"""
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


async def _validate_instruments_exist(db: AsyncSession, instrument_ids: list[int]) -> None:
    """批量校验乐器 ID 是否存在。"""
    if not instrument_ids:
        return
    stmt = select(Instrument.id).where(Instrument.id.in_(instrument_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(instrument_ids) - existing
    if missing:
        raise BusinessError(f"Instruments not found: {sorted(missing)}", 404)


async def _validate_emotion_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
    """批量校验情绪标签 ID 是否存在。"""
    if not tag_ids:
        return
    stmt = select(EmotionTag.id).where(EmotionTag.id.in_(tag_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(tag_ids) - existing
    if missing:
        raise BusinessError(f"Emotion tags not found: {sorted(missing)}", 404)


async def _validate_interest_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
    """批量校验兴趣标签 ID 是否存在。"""
    if not tag_ids:
        return
    stmt = select(InterestTag.id).where(InterestTag.id.in_(tag_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(tag_ids) - existing
    if missing:
        raise BusinessError(f"Interest tags not found: {sorted(missing)}", 404)


async def _set_music_instruments(
    db: AsyncSession, music: Music, instrument_ids: list[int]
) -> None:
    """设置音乐的乐器关联，覆盖原有乐器。"""
    await _validate_instruments_exist(db, instrument_ids)
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
    """设置音乐的情绪标签关联，覆盖原有标签。"""
    await _validate_emotion_tags_exist(db, tag_ids)
    await db.execute(
        delete(MusicEmotionTag).where(MusicEmotionTag.music_id == music.id)
    )
    for tag_id in tag_ids:
        db.add(MusicEmotionTag(music_id=music.id, emotion_tag_id=tag_id))


async def _set_music_interest_tags(
    db: AsyncSession, music: Music, tag_ids: list[int]
) -> None:
    """设置音乐的兴趣标签关联，覆盖原有标签。"""
    await _validate_interest_tags_exist(db, tag_ids)
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
        raise BusinessError(f"Invalid reference in music data: {exc}", 400)
    await db.refresh(music)
    return music


async def get_music_by_id(db: AsyncSession, music_id: int) -> Music | None:
    """根据 ID 获取音乐详情，加载所有关联关系。"""
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
    limit: int = 20,
    offset: int = 0,
) -> list[Music]:
    """分页列出音乐，支持筛选条件。默认只返回已上架音乐。"""
    stmt = (
        select(Music)
        .where(Music.is_published == is_published)
        .order_by(desc(Music.created_at))
        .limit(limit)
        .offset(offset)
    )
    if style_id is not None:
        stmt = stmt.where(Music.style_id == style_id)
    if language_id is not None:
        stmt = stmt.where(Music.language_id == language_id)
    if is_vip is not None:
        stmt = stmt.where(Music.is_vip == is_vip)

    # 列表只需加载作者关系
    stmt = stmt.options(
        selectinload(Music.authors).selectinload(MusicAuthor.author)
    )
    return list((await db.execute(stmt)).scalars().all())


async def search_musics(
    db: AsyncSession,
    *,
    q: str | None = None,
    is_published: bool = True,
    limit: int = 20,
    offset: int = 0,
) -> list[Music]:
    """按标题模糊搜索音乐。"""
    stmt = (
        select(Music)
        .where(Music.is_published == is_published)
        .order_by(desc(Music.hot))
        .limit(limit)
        .offset(offset)
    )
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Music.title.ilike(f"%{escaped_q}%", escape="\\"))

    stmt = stmt.options(
        selectinload(Music.authors).selectinload(MusicAuthor.author)
    )
    return list((await db.execute(stmt)).scalars().all())


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
) -> Music:
    """更新音乐文本信息及关联关系（不处理文件）。"""
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

    if author_ids is not None:
        await _set_music_authors(db, music, author_ids)
    if instrument_ids is not None:
        await _set_music_instruments(db, music, instrument_ids)
    if emotion_tag_ids is not None:
        await _set_music_emotion_tags(db, music, emotion_tag_ids)
    if interest_tag_ids is not None:
        await _set_music_interest_tags(db, music, interest_tag_ids)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BusinessError(f"Invalid reference in music data: {exc}", 400)
    await db.refresh(music)
    return music


async def set_music_published(db: AsyncSession, music: Music, published: bool) -> Music:
    """设置音乐上架/下架状态。"""
    music.is_published = published
    await db.commit()
    await db.refresh(music)
    return music
