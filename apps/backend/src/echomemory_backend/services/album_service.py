from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.album import (
    Album,
    AlbumAuthor,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
)
from echomemory_backend.models.dictionary import EmotionTag, InterestTag
from echomemory_backend.models.music import Music
from echomemory_backend.models.user import User
from echomemory_backend.services.user_service import BusinessError, get_user_by_id


async def _validate_emotion_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
    """批量校验情感标签 ID 是否存在。

    Args:
        db: SQLAlchemy 异步 Session。
        tag_ids: 待校验的情感标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的标签 ID 时抛出，状态码 404。
    """
    if not tag_ids:
        return
    stmt = select(EmotionTag.id).where(EmotionTag.id.in_(tag_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(tag_ids) - existing
    if missing:
        raise BusinessError(f"Emotion tags not found: {sorted(missing)}", 404)


async def _validate_interest_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
    """批量校验兴趣标签 ID 是否存在。

    Args:
        db: SQLAlchemy 异步 Session。
        tag_ids: 待校验的兴趣标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的标签 ID 时抛出，状态码 404。
    """
    if not tag_ids:
        return
    stmt = select(InterestTag.id).where(InterestTag.id.in_(tag_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(tag_ids) - existing
    if missing:
        raise BusinessError(f"Interest tags not found: {sorted(missing)}", 404)


async def _set_album_authors(
    db: AsyncSession, album: Album, author_ids: list[int]
) -> None:
    """设置专辑的作者关联，覆盖原有作者。

    Args:
        db: SQLAlchemy 异步 Session。
        album: 要设置作者的专辑实例。
        author_ids: 作者用户 ID 列表，按顺序关联。

    Returns:
        None。

    Raises:
        BusinessError: 某作者不存在或已被删除时抛出，状态码 404。
    """
    await db.execute(
        delete(AlbumAuthor).where(AlbumAuthor.album_id == album.id)
    )
    for ordinal, author_id in enumerate(author_ids):
        author = await get_user_by_id(db, author_id)
        if author is None or author.is_deleted:
            raise BusinessError(f"Author with id={author_id} not found", 404)
        db.add(
            AlbumAuthor(
                album_id=album.id, author_id=author_id, ordinal=ordinal
            )
        )


async def _set_album_emotion_tags(
    db: AsyncSession, album: Album, tag_ids: list[int]
) -> None:
    """设置专辑的情感标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        album: 要设置情感标签的专辑实例。
        tag_ids: 情感标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await _validate_emotion_tags_exist(db, tag_ids)
    await db.execute(
        delete(AlbumEmotionTag).where(AlbumEmotionTag.album_id == album.id)
    )
    for tag_id in tag_ids:
        db.add(AlbumEmotionTag(album_id=album.id, emotion_tag_id=tag_id))


async def _set_album_interest_tags(
    db: AsyncSession, album: Album, tag_ids: list[int]
) -> None:
    """设置专辑的兴趣标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        album: 要设置兴趣标签的专辑实例。
        tag_ids: 兴趣标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await _validate_interest_tags_exist(db, tag_ids)
    await db.execute(
        delete(AlbumInterestTag).where(AlbumInterestTag.album_id == album.id)
    )
    for tag_id in tag_ids:
        db.add(AlbumInterestTag(album_id=album.id, interest_tag_id=tag_id))


async def create_album(
    db: AsyncSession,
    *,
    title: str,
    description: str | None = None,
    source: str | None = None,
    cover_icon_url: str | None = None,
    cover_url: str | None = None,
    author_ids: list[int] | None = None,
) -> Album:
    """创建专辑及其关联关系。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        title: 专辑标题。
        description: 专辑描述，可选。
        source: 专辑来源，可选。
        cover_icon_url: 封面图标 URL，可选。
        cover_url: 封面 URL，可选。
        author_ids: 作者用户 ID 列表，可选。

    Returns:
        创建的专辑实例。

    Raises:
        BusinessError: 作者不存在或数据库约束冲突时抛出。
    """
    album = Album(
        title=title,
        description=description,
        source=source,
        cover_icon_url=cover_icon_url,
        cover_url=cover_url,
    )
    db.add(album)
    await db.flush()

    if author_ids:
        await _set_album_authors(db, album, author_ids)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BusinessError(f"Invalid reference in album data: {exc}", 400)
    await db.refresh(album)
    return album


async def get_album_by_id(db: AsyncSession, album_id: int) -> Album | None:
    """根据 ID 获取专辑详情，加载所有关联关系。

    Args:
        db: SQLAlchemy 异步 Session。
        album_id: 专辑主键 ID。

    Returns:
        专辑实例；不存在时返回 None。
    """
    stmt = (
        select(Album)
        .where(Album.id == album_id)
        .options(
            selectinload(Album.authors).selectinload(AlbumAuthor.author),
            selectinload(Album.musics).selectinload(AlbumMusic.music),
            selectinload(Album.emotion_tags).selectinload(
                AlbumEmotionTag.emotion_tag
            ),
            selectinload(Album.interest_tags).selectinload(
                AlbumInterestTag.interest_tag
            ),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_albums(
    db: AsyncSession,
    *,
    emotion_tag_id: int | None = None,
    interest_tag_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Album]:
    """分页列出未删除专辑，支持标签筛选。

    Args:
        db: SQLAlchemy 异步 Session。
        emotion_tag_id: 按情感标签筛选的标签 ID，可选。
        interest_tag_id: 按兴趣标签筛选的标签 ID，可选。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        专辑实例列表。
    """
    stmt = (
        select(Album)
        .where(Album.is_deleted == False)
        .order_by(desc(Album.created_at))
        .limit(limit)
        .offset(offset)
    )

    if emotion_tag_id is not None:
        stmt = stmt.where(
            Album.id.in_(
                select(AlbumEmotionTag.album_id).where(
                    AlbumEmotionTag.emotion_tag_id == emotion_tag_id
                )
            )
        )
    if interest_tag_id is not None:
        stmt = stmt.where(
            Album.id.in_(
                select(AlbumInterestTag.album_id).where(
                    AlbumInterestTag.interest_tag_id == interest_tag_id
                )
            )
        )

    return list((await db.execute(stmt)).scalars().all())


async def search_albums(
    db: AsyncSession,
    *,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Album]:
    """按标题模糊搜索未删除专辑。

    Args:
        db: SQLAlchemy 异步 Session。
        q: 搜索关键词，可选。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        匹配的专辑实例列表。
    """
    stmt = (
        select(Album)
        .where(Album.is_deleted == False)
        .order_by(desc(Album.hot))
        .limit(limit)
        .offset(offset)
    )
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Album.title.ilike(f"%{escaped_q}%", escape="\\"))
    return list((await db.execute(stmt)).scalars().all())


async def update_album(
    db: AsyncSession,
    album: Album,
    *,
    title: str | None = None,
    description: str | None = None,
    source: str | None = None,
    author_ids: list[int] | None = None,
) -> Album:
    """更新专辑文本信息及关联关系（不处理文件和标签）。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        album: 待更新的专辑实例。
        title: 新标题，可选。
        description: 新描述，可选。
        source: 新来源，可选。
        author_ids: 新的作者 ID 列表，可选，会覆盖原有作者。

    Returns:
        更新后的专辑实例。

    Raises:
        BusinessError: 作者不存在或数据库约束冲突时抛出。
    """
    if title is not None:
        album.title = title
    if description is not None:
        album.description = description
    if source is not None:
        album.source = source

    if author_ids is not None:
        await _set_album_authors(db, album, author_ids)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise BusinessError(f"Invalid reference in album data: {exc}", 400)
    await db.refresh(album)
    return album


async def soft_delete_album(db: AsyncSession, album: Album) -> None:
    """软删除专辑。

    Args:
        db: SQLAlchemy 异步 Session。
        album: 待删除的专辑实例。

    Returns:
        None。
    """
    album.is_deleted = True
    await db.commit()
    await db.refresh(album)


async def add_music_to_album(
    db: AsyncSession, album_id: int, music_id: int
) -> AlbumMusic:
    """将一首已上架音乐加入专辑。

    校验音乐存在且已发布；拒绝重复添加；处理音乐已属于其他专辑的冲突。

    Args:
        db: SQLAlchemy 异步 Session。
        album_id: 目标专辑 ID。
        music_id: 要添加的音乐 ID。

    Returns:
        创建的 AlbumMusic 关联实例。

    Raises:
        BusinessError: 音乐不存在或未发布时抛出 404；音乐已在专辑中时抛出 409；
            音乐已属于其他专辑时抛出 409。
    """
    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    existing = await db.get(AlbumMusic, (album_id, music_id))
    if existing is not None:
        raise BusinessError("Music already in album", 409)

    stmt = select(func.max(AlbumMusic.ordinal)).where(
        AlbumMusic.album_id == album_id
    )
    max_ordinal = (await db.execute(stmt)).scalar_one_or_none() or 0

    album_music = AlbumMusic(
        album_id=album_id, music_id=music_id, ordinal=max_ordinal + 1
    )
    db.add(album_music)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError(
            "Music already belongs to another album", 409
        )
    await db.refresh(album_music)
    return album_music


async def remove_music_from_album(
    db: AsyncSession, album_id: int, music_id: int
) -> None:
    """从专辑移除一首音乐。

    若关联记录不存在，抛出 BusinessError(404)。

    Args:
        db: SQLAlchemy 异步 Session。
        album_id: 目标专辑 ID。
        music_id: 要移除的音乐 ID。

    Returns:
        None。

    Raises:
        BusinessError: 关联记录不存在时抛出，状态码 404。
    """
    album_music = await db.get(AlbumMusic, (album_id, music_id))
    if album_music is None:
        raise BusinessError("Music not found in album", 404)

    await db.delete(album_music)
    await db.commit()
