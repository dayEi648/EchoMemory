from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.dictionary import EmotionTag, InterestTag
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.services.user_service import BusinessError


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


async def _set_playlist_emotion_tags(
    db: AsyncSession, playlist: Playlist, tag_ids: list[int]
) -> None:
    """设置歌单的情感标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 要设置情感标签的歌单实例。
        tag_ids: 情感标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await _validate_emotion_tags_exist(db, tag_ids)
    await db.execute(
        delete(PlaylistEmotionTag).where(PlaylistEmotionTag.playlist_id == playlist.id)
    )
    for tag_id in tag_ids:
        db.add(PlaylistEmotionTag(playlist_id=playlist.id, emotion_tag_id=tag_id))


async def _set_playlist_interest_tags(
    db: AsyncSession, playlist: Playlist, tag_ids: list[int]
) -> None:
    """设置歌单的兴趣标签关联，覆盖原有标签。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 要设置兴趣标签的歌单实例。
        tag_ids: 兴趣标签 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 某标签不存在时抛出，状态码 404。
    """
    await _validate_interest_tags_exist(db, tag_ids)
    await db.execute(
        delete(PlaylistInterestTag).where(PlaylistInterestTag.playlist_id == playlist.id)
    )
    for tag_id in tag_ids:
        db.add(PlaylistInterestTag(playlist_id=playlist.id, interest_tag_id=tag_id))


async def create_playlist(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    description: str | None = None,
    is_private: bool = False,
    cover_icon_url: str | None = None,
) -> Playlist:
    """创建歌单。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 创建者用户 ID。
        title: 歌单标题。
        description: 歌单描述，可选。
        is_private: 是否私密，默认 False。
        cover_icon_url: 封面图标 URL，可选。

    Returns:
        创建的歌单实例。
    """
    playlist = Playlist(
        title=title,
        user_id=user_id,
        description=description,
        is_private=is_private,
        cover_icon_url=cover_icon_url,
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist


async def get_playlist_by_id(db: AsyncSession, playlist_id: int) -> Playlist | None:
    """根据 ID 获取歌单详情，加载所有关联关系。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 歌单主键 ID。

    Returns:
        歌单实例；不存在时返回 None。
    """
    stmt = (
        select(Playlist)
        .where(Playlist.id == playlist_id)
        .options(
            selectinload(Playlist.user),
            selectinload(Playlist.musics).selectinload(PlaylistMusic.music),
            selectinload(Playlist.emotion_tags).selectinload(
                PlaylistEmotionTag.emotion_tag
            ),
            selectinload(Playlist.interest_tags).selectinload(
                PlaylistInterestTag.interest_tag
            ),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_user_playlists(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[Playlist]:
    """查询指定用户的歌单列表，按创建时间倒序。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键 ID。
        limit: 返回数量上限，默认 20。
        offset: 分页偏移量，默认 0。

    Returns:
        歌单实例列表。
    """
    stmt = (
        select(Playlist)
        .where(Playlist.user_id == user_id)
        .order_by(desc(Playlist.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(Playlist.user))
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_playlist(
    db: AsyncSession,
    playlist: Playlist,
    *,
    title: str | None = None,
    description: str | None = None,
    is_private: bool | None = None,
) -> Playlist:
    """更新歌单文本字段。

    标签由系统根据歌曲收藏自动计算，不允许手动传入。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 待更新的歌单实例。
        title: 新标题，可选。
        description: 新描述，可选。
        is_private: 新隐私状态，可选。

    Returns:
        更新后的歌单实例。
    """
    if title is not None:
        playlist.title = title
    if description is not None:
        playlist.description = description
    if is_private is not None:
        playlist.is_private = is_private

    await db.commit()
    await db.refresh(playlist)
    return playlist


async def delete_playlist(db: AsyncSession, playlist: Playlist) -> None:
    """删除歌单（级联删除关联表记录）。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist: 待删除的歌单实例。

    Returns:
        None。
    """
    await db.delete(playlist)
    await db.commit()


async def add_music_to_playlist(
    db: AsyncSession, playlist_id: int, music_id: int
) -> PlaylistMusic:
    """添加一首音乐到歌单。

    校验音乐存在且已发布；查询当前最大 ordinal 并 +1；拒绝重复添加。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 目标歌单 ID。
        music_id: 要添加的音乐 ID。

    Returns:
        创建的 PlaylistMusic 关联实例。

    Raises:
        BusinessError: 音乐不存在或未发布时抛出 404；音乐已在歌单中时抛出 409。
    """
    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    existing = await db.get(PlaylistMusic, (playlist_id, music_id))
    if existing is not None:
        raise BusinessError("Music already in playlist", 409)

    stmt = select(func.max(PlaylistMusic.ordinal)).where(
        PlaylistMusic.playlist_id == playlist_id
    )
    max_ordinal = (await db.execute(stmt)).scalar_one_or_none() or 0

    playlist_music = PlaylistMusic(
        playlist_id=playlist_id, music_id=music_id, ordinal=max_ordinal + 1
    )
    db.add(playlist_music)
    await db.commit()
    await db.refresh(playlist_music)
    return playlist_music


async def remove_music_from_playlist(
    db: AsyncSession, playlist_id: int, music_id: int
) -> None:
    """从歌单移除一首音乐。

    若关联记录不存在，抛出 BusinessError(404)。

    Args:
        db: SQLAlchemy 异步 Session。
        playlist_id: 目标歌单 ID。
        music_id: 要移除的音乐 ID。

    Returns:
        None。

    Raises:
        BusinessError: 关联记录不存在时抛出，状态码 404。
    """
    playlist_music = await db.get(PlaylistMusic, (playlist_id, music_id))
    if playlist_music is None:
        raise BusinessError("Music not found in playlist", 404)

    await db.delete(playlist_music)
    await db.commit()
