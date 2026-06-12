"""用户收藏服务模块，提供音乐、专辑、歌单的收藏/取消收藏以及已发布音乐标记功能。"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.album import Album
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.core.exceptions import BusinessError


@dataclass
class MusicCollectionView:
    """歌曲收藏视图：由歌单归属关系派生，供 MusicCollectionOut 序列化。"""

    music: Music
    created_at: datetime


# ---------------------------------------------------------------------------
# 音乐收藏（派生自用户歌单归属，非独立收藏表）
# ---------------------------------------------------------------------------


async def _get_music_collection_view(
    db: AsyncSession, user_id: int, music_id: int
) -> MusicCollectionView:
    """加载用户收藏歌曲的视图（取最近一次加入歌单的时间）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        含音乐详情与最近加入时间的收藏视图。

    Raises:
        BusinessError: 歌曲不在用户任一歌单中时抛出 404。
    """
    stmt = (
        select(PlaylistMusic)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(
            Playlist.user_id == user_id,
            PlaylistMusic.music_id == music_id,
        )
        .order_by(desc(PlaylistMusic.created_at))
        .limit(1)
        .options(
            selectinload(PlaylistMusic.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    playlist_music = (await db.execute(stmt)).scalar_one_or_none()
    if playlist_music is None:
        raise BusinessError("Music not found in user playlists", 404)
    return MusicCollectionView(
        music=playlist_music.music,
        created_at=playlist_music.created_at,
    )


async def collect_music(db: AsyncSession, user_id: int, music_id: int) -> MusicCollectionView:
    """收藏音乐：加入用户默认「我喜欢的音乐」歌单。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        收藏视图（已存在于任一歌单时返回现有记录）。

    Raises:
        BusinessError: 音乐不存在或未发布时抛出 404。
    """
    from echomemory_backend.services import playlist_service

    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    if await is_music_collected(db, user_id, music_id):
        return await _get_music_collection_view(db, user_id, music_id)

    like_playlist = await playlist_service.create_default_like_playlist(db, user_id)
    await playlist_service.add_music_to_playlist(db, like_playlist.id, music_id)
    return await _get_music_collection_view(db, user_id, music_id)


async def uncollect_music(db: AsyncSession, user_id: int, music_id: int) -> None:
    """取消收藏音乐：从用户全部歌单中移除该歌曲。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        None。
    """
    from echomemory_backend.services import playlist_service

    stmt = (
        select(PlaylistMusic.playlist_id)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(
            Playlist.user_id == user_id,
            PlaylistMusic.music_id == music_id,
        )
    )
    playlist_ids = list((await db.execute(stmt)).scalars().all())
    for playlist_id in playlist_ids:
        await playlist_service.remove_music_from_playlist(db, playlist_id, music_id)


async def list_music_collections(
    db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0
) -> dict[str, object]:
    """查询用户的收藏音乐列表（存在于任一歌单中的去重歌曲）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按最近加入歌单时间倒序的 MusicCollectionView 列表, "total": 总记录数}。
    """
    latest_subq = (
        select(
            PlaylistMusic.music_id.label("music_id"),
            func.max(PlaylistMusic.created_at).label("created_at"),
        )
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(Playlist.user_id == user_id)
        .group_by(PlaylistMusic.music_id)
        .subquery()
    )

    total = (
        await db.execute(select(func.count()).select_from(latest_subq))
    ).scalar_one()

    rows = (
        await db.execute(
            select(latest_subq.c.music_id, latest_subq.c.created_at)
            .order_by(desc(latest_subq.c.created_at))
            .limit(limit)
            .offset(offset)
        )
    ).all()

    if not rows:
        return {"items": [], "total": total}

    music_ids = [row.music_id for row in rows]
    created_at_map = {row.music_id: row.created_at for row in rows}

    music_stmt = (
        select(Music)
        .where(Music.id.in_(music_ids))
        .options(
            selectinload(Music.authors).selectinload(MusicAuthor.author),
        )
    )
    musics = {
        music.id: music
        for music in (await db.execute(music_stmt)).scalars().all()
    }

    items = [
        MusicCollectionView(music=musics[music_id], created_at=created_at_map[music_id])
        for music_id in music_ids
        if music_id in musics
    ]
    return {"items": items, "total": total}


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
    await db.execute(
        update(Album)
        .where(Album.id == album_id)
        .values(collect_count=Album.collect_count + 1)
    )
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
        .limit(limit)
        .offset(offset)
        .options(selectinload(UserAlbumCollection.album))
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


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
        raise BusinessError("Playlist not found", 404)
    if playlist.user_id == user_id:
        raise BusinessError("Cannot collect your own playlist", 403)

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
    if music is None or not music.is_published:
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
) -> dict[str, object]:
    """查询用户的已发布音乐列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按标记时间倒序的 UserMusicRelease 列表, "total": 总记录数}。
    """
    where_clause = [UserMusicRelease.user_id == user_id]
    stmt = (
        select(UserMusicRelease)
        .where(*where_clause)
        .order_by(desc(UserMusicRelease.created_at))
        .limit(limit)
        .offset(offset)
        .options(
            selectinload(UserMusicRelease.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


async def is_music_collected(db: AsyncSession, user_id: int, music_id: int) -> bool:
    """判断用户是否已收藏指定音乐（存在于任一歌单即为已收藏）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。

    Returns:
        已收藏返回 True，否则返回 False。
    """
    stmt = (
        select(func.count())
        .select_from(PlaylistMusic)
        .join(Playlist, PlaylistMusic.playlist_id == Playlist.id)
        .where(
            Playlist.user_id == user_id,
            PlaylistMusic.music_id == music_id,
        )
    )
    return (await db.execute(stmt)).scalar_one() > 0


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
