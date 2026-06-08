from sqlalchemy import delete, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.music import Music
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.core.exceptions import BusinessError


async def create_play_history(
    db: AsyncSession, user_id: int, music_id: int, playlist_id: int | None = None
) -> PlayHistory:
    """创建一条播放历史记录，并原子递增对应音乐、专辑及歌单的播放次数。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        music_id: 音乐主键。
        playlist_id: 歌单主键，可选。若提供则校验歌单存在且包含该歌曲。

    Returns:
        创建后的 PlayHistory 实例。

    Raises:
        BusinessError: 音乐不存在或未上架时抛出 404；歌单不存在时抛出 404；
                       歌曲不在歌单中时抛出 400。
    """
    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    if playlist_id is not None:
        playlist = await db.get(Playlist, playlist_id)
        if playlist is None:
            raise BusinessError("Playlist not found", 404)
        stmt = select(PlaylistMusic).where(
            PlaylistMusic.playlist_id == playlist_id,
            PlaylistMusic.music_id == music_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise BusinessError("Music not in playlist", 400)

    history = PlayHistory(user_id=user_id, music_id=music_id)
    db.add(history)

    # 递增音乐播放量
    await db.execute(
        update(Music)
        .where(Music.id == music_id)
        .values(play_count=Music.play_count + 1)
    )

    # 递增所属专辑播放量（一首歌仅属于一个专辑）
    stmt = select(AlbumMusic.album_id).where(AlbumMusic.music_id == music_id)
    result = await db.execute(stmt)
    album_id = result.scalar_one_or_none()
    if album_id is not None:
        await db.execute(
            update(Album)
            .where(Album.id == album_id, Album.is_deleted.is_(False))
            .values(play_count=Album.play_count + 1)
        )

    # 递增歌单播放量（如提供）
    if playlist_id is not None:
        await db.execute(
            update(Playlist)
            .where(Playlist.id == playlist_id)
            .values(play_count=Playlist.play_count + 1)
        )

    await db.commit()

    # 自动重新计算用户标签
    from echomemory_backend.services.user_tag_service import recalculate_user_tags

    await recalculate_user_tags(db, user_id)

    await db.refresh(history)
    return history


async def list_play_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[PlayHistory]:
    """查询用户的播放历史。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        按播放时间倒序、关联加载音乐信息的 PlayHistory 列表。
    """
    stmt = (
        select(PlayHistory)
        .where(PlayHistory.user_id == user_id)
        .order_by(desc(PlayHistory.played_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(PlayHistory.music))
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_play_history(
    db: AsyncSession, user_id: int, history_id: int
) -> None:
    """删除单条播放历史。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        history_id: 播放历史记录主键。

    Returns:
        None。

    Raises:
        BusinessError: 记录不存在或不属于该用户时抛出 404。
    """
    history = await db.get(PlayHistory, history_id)
    if history is None or history.user_id != user_id:
        raise BusinessError("Play history record not found", 404)

    await db.delete(history)
    await db.commit()


async def clear_play_history(db: AsyncSession, user_id: int) -> None:
    """清空该用户的全部播放历史。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        None。
    """
    await db.execute(
        delete(PlayHistory).where(PlayHistory.user_id == user_id)
    )
    await db.commit()
