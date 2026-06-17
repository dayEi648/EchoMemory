"""用户收藏服务模块，提供音乐喜欢、专辑收藏、歌单收藏功能。"""
from echomemory_backend.core.exceptions.codes import ErrorCode

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, delete, desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.db.pagination import paginate
from echomemory_backend.models.album import Album
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicLike,
    UserPlaylistCollection,
)
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.core.exceptions.business import BusinessError


@dataclass
class MusicCollectionView:
    """歌曲喜欢视图：供 MusicCollectionOut 序列化。"""

    music: Music
    created_at: datetime


# ---------------------------------------------------------------------------
# 音乐喜欢
# ---------------------------------------------------------------------------


async def _get_music_collection_view(
    db: AsyncSession, user_id: int, music_id: int
) -> MusicCollectionView:
    """加载用户喜欢歌曲的视图。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        含音乐详情与最近加入时间的收藏视图。

    Raises:
        BusinessError: 歌曲不在用户喜欢列表中时抛出 404。
    """
    stmt = (
        select(UserMusicLike)
        .where(
            UserMusicLike.user_id == user_id,
            UserMusicLike.music_id == music_id,
        )
        .options(
            selectinload(UserMusicLike.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    like = (await db.execute(stmt)).scalar_one_or_none()
    if like is None:
        raise BusinessError("Music not found in user likes", code=ErrorCode.MUSIC_NOT_IN_USER_PLAYLISTS)
    return MusicCollectionView(
        music=like.music,
        created_at=like.created_at,
    )


async def uncollect_music(db: AsyncSession, user_id: int, music_id: int) -> None:
    """取消喜欢音乐：从用户默认喜欢歌单和喜欢表中移除该歌曲。
    在同一事务内删除喜欢表记录与默认喜欢歌单中的关联记录，避免部分成功。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        None。
    """
    from echomemory_backend.services.cache_service import (
        invalidate_music_detail,
        invalidate_playlist_detail,
    )
    from echomemory_backend.services.hotness_service import (
        recalculate_music_hot,
        recalculate_playlist_hot,
    )
    from echomemory_backend.services.playlist_service import _sync_playlist_tags_from_musics
    from echomemory_backend.services.user_tag_service import recalculate_user_tags

    like = await db.get(UserMusicLike, (user_id, music_id))

    like_playlist_stmt = (
        select(Playlist.id)
        .where(Playlist.user_id == user_id, Playlist.is_like.is_(True))
        .limit(1)
    )
    like_playlist_id = (await db.execute(like_playlist_stmt)).scalar_one_or_none()

    playlist_ids: list[int] = []
    if like_playlist_id is not None:
        existing_member = await db.get(PlaylistMusic, (like_playlist_id, music_id))
        if existing_member is not None:
            playlist_ids.append(like_playlist_id)

    if like is None and not playlist_ids:
        return

    like_removed = like is not None
    if like_removed:
        await db.delete(like)
        await db.execute(
            update(Music)
            .where(Music.id == music_id)
            .values(
                collect_count=case(
                    (Music.collect_count > 0, Music.collect_count - 1),
                    else_=0,
                )
            )
        )

    if like_playlist_id is not None:
        await db.execute(
            delete(PlaylistMusic).where(
                PlaylistMusic.playlist_id == like_playlist_id,
                PlaylistMusic.music_id == music_id,
            )
        )
    await db.flush()

    if like_removed:
        await recalculate_music_hot(db, music_id)
    for playlist_id in playlist_ids:
        await _sync_playlist_tags_from_musics(db, playlist_id)
        await recalculate_playlist_hot(db, playlist_id)

    await recalculate_user_tags(db, user_id, commit=False)
    await db.commit()

    if like_removed:
        await invalidate_music_detail(music_id)
    for playlist_id in playlist_ids:
        await invalidate_playlist_detail(playlist_id)


async def list_music_collections(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> dict[str, object]:
    """查询用户的喜欢音乐列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按喜欢时间倒序的 MusicCollectionView 列表, "total": 总记录数}。
    """
    where_clause = [UserMusicLike.user_id == user_id]
    stmt = (
        select(UserMusicLike)
        .where(*where_clause)
        .order_by(desc(UserMusicLike.created_at))
        .options(
            selectinload(UserMusicLike.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    items = [
        MusicCollectionView(music=like.music, created_at=like.created_at)
        for like in page.items
    ]
    return {"items": items, "total": page.total}


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
        raise BusinessError("Album not found", code=ErrorCode.ALBUM_NOT_FOUND)

    existing = await db.get(UserAlbumCollection, (user_id, album_id))
    if existing is not None:
        return await _get_album_collection_with_relations(db, user_id, album_id)

    collection = UserAlbumCollection(user_id=user_id, album_id=album_id)
    db.add(collection)
    await db.execute(
        update(Album)
        .where(Album.id == album_id)
        .values(collect_count=Album.collect_count + 1)
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return await _get_album_collection_with_relations(db, user_id, album_id)
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
) -> dict[str, object]:
    """查询用户的收藏专辑列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按收藏时间倒序的 UserAlbumCollection 列表, "total": 总记录数}。
    """
    where_clause = [UserAlbumCollection.user_id == user_id]
    stmt = (
        select(UserAlbumCollection)
        .where(*where_clause)
        .order_by(desc(UserAlbumCollection.created_at))
        .options(selectinload(UserAlbumCollection.album))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


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
        BusinessError: 歌单不存在或未公开时抛出 404；收藏自己的歌单时抛出 403。
    """
    playlist = await db.get(Playlist, playlist_id)
    if playlist is None or playlist.is_private:
        raise BusinessError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND)
    if playlist.user_id == user_id:
        raise BusinessError("Cannot collect your own playlist", code=ErrorCode.CANNOT_COLLECT_OWN_PLAYLIST)

    existing = await db.get(UserPlaylistCollection, (user_id, playlist_id))
    if existing is not None:
        return await _get_playlist_collection_with_relations(db, user_id, playlist_id)

    collection = UserPlaylistCollection(user_id=user_id, playlist_id=playlist_id)
    db.add(collection)
    await db.execute(
        update(Playlist)
        .where(Playlist.id == playlist_id)
        .values(collect_count=Playlist.collect_count + 1)
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return await _get_playlist_collection_with_relations(db, user_id, playlist_id)
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
) -> dict[str, object]:
    """查询用户的收藏歌单列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按收藏时间倒序的 UserPlaylistCollection 列表, "total": 总记录数}。
    """
    where_clause = [
        UserPlaylistCollection.user_id == user_id,
        Playlist.user_id != user_id,
    ]
    stmt = (
        select(UserPlaylistCollection)
        .join(Playlist, UserPlaylistCollection.playlist_id == Playlist.id)
        .where(*where_clause)
        .order_by(desc(UserPlaylistCollection.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(UserPlaylistCollection.playlist).selectinload(Playlist.user))
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count())
            .select_from(UserPlaylistCollection)
            .join(Playlist, UserPlaylistCollection.playlist_id == Playlist.id)
            .where(*where_clause)
        )
    ).scalar_one()
    return {"items": items, "total": total}


async def is_music_collected(db: AsyncSession, user_id: int, music_id: int) -> bool:
    """判断用户是否已喜欢指定音乐。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        已收藏返回 True，否则返回 False。
    """
    return await db.get(UserMusicLike, (user_id, music_id)) is not None


async def is_album_collected(db: AsyncSession, user_id: int, album_id: int) -> bool:
    """判断用户是否已收藏指定专辑。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        album_id: 专辑主键。

    Returns:
        已收藏返回 True，否则返回 False。
    """
    return await db.get(UserAlbumCollection, (user_id, album_id)) is not None


async def is_playlist_collected(db: AsyncSession, user_id: int, playlist_id: int) -> bool:
    """判断用户是否已收藏指定歌单（自己的歌单恒为未收藏）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        playlist_id: 歌单主键。

    Returns:
        已收藏返回 True，否则返回 False。
    """
    playlist = await db.get(Playlist, playlist_id)
    if playlist is None or playlist.user_id == user_id:
        return False
    return await db.get(UserPlaylistCollection, (user_id, playlist_id)) is not None


async def get_collected_music_ids(
    db: AsyncSession, user_id: int, music_ids: list[int]
) -> set[int]:
    """批量判断一组音乐中哪些已被用户喜欢。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_ids: 音乐主键列表。

    Returns:
        已被喜欢的音乐 ID 集合。
    """
    if not music_ids:
        return set()
    stmt = (
        select(UserMusicLike.music_id)
        .where(
            UserMusicLike.user_id == user_id,
            UserMusicLike.music_id.in_(music_ids),
        )
    )
    rows = await db.execute(stmt)
    return set(rows.scalars().all())


async def get_collected_album_ids(
    db: AsyncSession, user_id: int, album_ids: list[int]
) -> set[int]:
    """批量判断一组专辑中哪些已被用户收藏。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        album_ids: 专辑主键列表。

    Returns:
        已被收藏的专辑 ID 集合。
    """
    if not album_ids:
        return set()
    stmt = (
        select(UserAlbumCollection.album_id)
        .where(
            UserAlbumCollection.user_id == user_id,
            UserAlbumCollection.album_id.in_(album_ids),
        )
    )
    rows = await db.execute(stmt)
    return set(rows.scalars().all())


async def get_collected_playlist_ids(
    db: AsyncSession, user_id: int, playlist_ids: list[int]
) -> set[int]:
    """批量判断一组歌单中哪些已被用户收藏（自己的歌单恒为未收藏）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        playlist_ids: 歌单主键列表。

    Returns:
        已被收藏的歌单 ID 集合。
    """
    if not playlist_ids:
        return set()
    stmt = (
        select(UserPlaylistCollection.playlist_id)
        .where(
            UserPlaylistCollection.user_id == user_id,
            UserPlaylistCollection.playlist_id.in_(playlist_ids),
        )
    )
    rows = await db.execute(stmt)
    collected = set(rows.scalars().all())
    # 自己的歌单不算收藏
    own_stmt = select(Playlist.id).where(
        Playlist.id.in_(playlist_ids),
        Playlist.user_id == user_id,
    )
    own_rows = await db.execute(own_stmt)
    collected -= set(own_rows.scalars().all())
    return collected
