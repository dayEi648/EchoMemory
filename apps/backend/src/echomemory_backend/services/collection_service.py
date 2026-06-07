from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.album import Album
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.services.user_service import BusinessError


# ---------------------------------------------------------------------------
# 音乐收藏
# ---------------------------------------------------------------------------


async def _get_music_collection_with_relations(
    db: AsyncSession, user_id: int, music_id: int
) -> UserMusicCollection:
    """加载完整关联后的 UserMusicCollection 记录。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        关联加载完整的 UserMusicCollection 实例。
    """
    stmt = (
        select(UserMusicCollection)
        .where(
            UserMusicCollection.user_id == user_id,
            UserMusicCollection.music_id == music_id,
        )
        .options(
            selectinload(UserMusicCollection.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def collect_music(db: AsyncSession, user_id: int, music_id: int) -> UserMusicCollection:
    """收藏音乐。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        收藏记录实例（已存在时返回现有记录）。

    Raises:
        BusinessError: 音乐不存在时抛出 404。
    """
    music = await db.get(Music, music_id)
    if music is None:
        raise BusinessError("Music not found", 404)

    existing = await db.get(UserMusicCollection, (user_id, music_id))
    if existing is not None:
        return await _get_music_collection_with_relations(db, user_id, music_id)

    collection = UserMusicCollection(user_id=user_id, music_id=music_id)
    db.add(collection)
    await db.commit()
    return await _get_music_collection_with_relations(db, user_id, music_id)


async def uncollect_music(db: AsyncSession, user_id: int, music_id: int) -> None:
    """取消收藏音乐。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        None。
    """
    existing = await db.get(UserMusicCollection, (user_id, music_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def list_music_collections(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> list[UserMusicCollection]:
    """查询用户的收藏音乐列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        按收藏时间倒序排列的 UserMusicCollection 列表。
    """
    stmt = (
        select(UserMusicCollection)
        .where(UserMusicCollection.user_id == user_id)
        .order_by(desc(UserMusicCollection.created_at))
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(UserMusicCollection.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# 专辑收藏
# ---------------------------------------------------------------------------


async def _get_album_collection_with_relations(
    db: AsyncSession, user_id: int, album_id: int
) -> UserAlbumCollection:
    """加载完整关联后的 UserAlbumCollection 记录。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        album_id: 专辑主键。

    Returns:
        关联加载完整的 UserAlbumCollection 实例。
    """
    stmt = (
        select(UserAlbumCollection)
        .where(
            UserAlbumCollection.user_id == user_id,
            UserAlbumCollection.album_id == album_id,
        )
        .options(selectinload(UserAlbumCollection.album))
    )
    return (await db.execute(stmt)).scalar_one()


async def collect_album(db: AsyncSession, user_id: int, album_id: int) -> UserAlbumCollection:
    """收藏专辑。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        album_id: 专辑主键。

    Returns:
        收藏记录实例（已存在时返回现有记录）。

    Raises:
        BusinessError: 专辑不存在时抛出 404。
    """
    album = await db.get(Album, album_id)
    if album is None or album.is_deleted:
        raise BusinessError("Album not found", 404)

    existing = await db.get(UserAlbumCollection, (user_id, album_id))
    if existing is not None:
        return await _get_album_collection_with_relations(db, user_id, album_id)

    collection = UserAlbumCollection(user_id=user_id, album_id=album_id)
    db.add(collection)
    await db.commit()
    return await _get_album_collection_with_relations(db, user_id, album_id)


async def uncollect_album(db: AsyncSession, user_id: int, album_id: int) -> None:
    """取消收藏专辑。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        album_id: 专辑主键。

    Returns:
        None。
    """
    existing = await db.get(UserAlbumCollection, (user_id, album_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def list_album_collections(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> list[UserAlbumCollection]:
    """查询用户的收藏专辑列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        按收藏时间倒序排列的 UserAlbumCollection 列表。
    """
    stmt = (
        select(UserAlbumCollection)
        .where(UserAlbumCollection.user_id == user_id)
        .order_by(desc(UserAlbumCollection.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(UserAlbumCollection.album))
    )
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# 歌单收藏
# ---------------------------------------------------------------------------


async def _get_playlist_collection_with_relations(
    db: AsyncSession, user_id: int, playlist_id: int
) -> UserPlaylistCollection:
    """加载完整关联后的 UserPlaylistCollection 记录。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        playlist_id: 歌单主键。

    Returns:
        关联加载完整的 UserPlaylistCollection 实例。
    """
    stmt = (
        select(UserPlaylistCollection)
        .where(
            UserPlaylistCollection.user_id == user_id,
            UserPlaylistCollection.playlist_id == playlist_id,
        )
        .options(selectinload(UserPlaylistCollection.playlist).selectinload(Playlist.user))
    )
    return (await db.execute(stmt)).scalar_one()


async def collect_playlist(
    db: AsyncSession, user_id: int, playlist_id: int
) -> UserPlaylistCollection:
    """收藏歌单。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        playlist_id: 歌单主键。

    Returns:
        收藏记录实例（已存在时返回现有记录）。

    Raises:
        BusinessError: 歌单不存在时抛出 404。
    """
    playlist = await db.get(Playlist, playlist_id)
    if playlist is None:
        raise BusinessError("Playlist not found", 404)

    existing = await db.get(UserPlaylistCollection, (user_id, playlist_id))
    if existing is not None:
        return await _get_playlist_collection_with_relations(db, user_id, playlist_id)

    collection = UserPlaylistCollection(user_id=user_id, playlist_id=playlist_id)
    db.add(collection)
    await db.commit()
    return await _get_playlist_collection_with_relations(db, user_id, playlist_id)


async def uncollect_playlist(db: AsyncSession, user_id: int, playlist_id: int) -> None:
    """取消收藏歌单。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        playlist_id: 歌单主键。

    Returns:
        None。
    """
    existing = await db.get(UserPlaylistCollection, (user_id, playlist_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def list_playlist_collections(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> list[UserPlaylistCollection]:
    """查询用户的收藏歌单列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        按收藏时间倒序排列的 UserPlaylistCollection 列表。
    """
    stmt = (
        select(UserPlaylistCollection)
        .where(UserPlaylistCollection.user_id == user_id)
        .order_by(desc(UserPlaylistCollection.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(UserPlaylistCollection.playlist).selectinload(Playlist.user))
    )
    return list((await db.execute(stmt)).scalars().all())


# ---------------------------------------------------------------------------
# 已发布音乐标记
# ---------------------------------------------------------------------------


async def _get_release_with_relations(
    db: AsyncSession, user_id: int, music_id: int
) -> UserMusicRelease:
    """加载完整关联后的 UserMusicRelease 记录。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        关联加载完整的 UserMusicRelease 实例。
    """
    stmt = (
        select(UserMusicRelease)
        .where(
            UserMusicRelease.user_id == user_id,
            UserMusicRelease.music_id == music_id,
        )
        .options(
            selectinload(UserMusicRelease.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    return (await db.execute(stmt)).scalar_one()


async def release_music(db: AsyncSession, user_id: int, music_id: int) -> UserMusicRelease:
    """标记音乐为已发布。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        已发布记录实例（已存在时返回现有记录）。

    Raises:
        BusinessError: 音乐不存在时抛出 404。
    """
    music = await db.get(Music, music_id)
    if music is None:
        raise BusinessError("Music not found", 404)

    existing = await db.get(UserMusicRelease, (user_id, music_id))
    if existing is not None:
        return await _get_release_with_relations(db, user_id, music_id)

    release = UserMusicRelease(user_id=user_id, music_id=music_id)
    db.add(release)
    await db.commit()
    return await _get_release_with_relations(db, user_id, music_id)


async def unrelease_music(db: AsyncSession, user_id: int, music_id: int) -> None:
    """取消已发布音乐标记。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        None。
    """
    existing = await db.get(UserMusicRelease, (user_id, music_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def list_releases(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> list[UserMusicRelease]:
    """查询用户的已发布音乐列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        按标记时间倒序排列的 UserMusicRelease 列表。
    """
    stmt = (
        select(UserMusicRelease)
        .where(UserMusicRelease.user_id == user_id)
        .order_by(desc(UserMusicRelease.created_at))
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(UserMusicRelease.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    return list((await db.execute(stmt)).scalars().all())
