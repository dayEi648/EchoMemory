"""播放历史服务层。

提供播放历史记录的创建、查询、删除及清空等核心业务逻辑，
并在创建播放历史时同步递增音乐、专辑和歌单的播放次数。
"""
from echomemory_backend.core.exceptions.codes import ErrorCode

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.db.pagination import paginate
from echomemory_backend.models.album import Album, AlbumMusic
from echomemory_backend.models.music import Music, MusicAuthor
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import Playlist, PlaylistMusic
from echomemory_backend.services.cache_service import invalidate_music_detail


MAX_PLAY_HISTORY_ITEMS = 100


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
        raise BusinessError("Music not found", code=ErrorCode.MUSIC_NOT_FOUND)

    if playlist_id is not None:
        playlist = await db.get(Playlist, playlist_id)
        if playlist is None:
            raise BusinessError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND)
        stmt = select(PlaylistMusic).where(
            PlaylistMusic.playlist_id == playlist_id,
            PlaylistMusic.music_id == music_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise BusinessError("Music not in playlist", code=ErrorCode.MUSIC_NOT_IN_PLAYLIST)

    insert_stmt = (
        pg_insert(PlayHistory)
        .values(user_id=user_id, music_id=music_id, play_count=1)
        .on_conflict_do_update(
            index_elements=["user_id", "music_id"],
            set_={
                "play_count": PlayHistory.play_count + 1,
                "played_at": func.now(),
            },
        )
        .returning(PlayHistory.id)
    )
    history_id = (await db.execute(insert_stmt)).scalar_one()
    history = await db.get(PlayHistory, history_id)
    if history is None:
        raise BusinessError(
            "Failed to record play history", code=ErrorCode.SYSTEM_INTERNAL_ERROR
        )
    await db.flush()

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

    await _prune_user_play_history(db, user_id)

    # 自动重新计算热度（与主业务同事务提交）
    from echomemory_backend.services.hotness_service import recalculate_music_hot

    await recalculate_music_hot(db, music_id)

    # 自动重新计算用户标签（与主业务同事务提交）
    from echomemory_backend.services.user_tag_service import recalculate_user_tags

    await recalculate_user_tags(db, user_id, commit=False)

    await db.commit()
    stmt = (
        select(PlayHistory)
        .where(PlayHistory.id == history.id)
        .options(
            selectinload(PlayHistory.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    history = (await db.execute(stmt)).scalar_one()
    await invalidate_music_detail(music_id)
    return history


async def _prune_user_play_history(db: AsyncSession, user_id: int) -> None:
    """裁剪用户播放历史，只保留最近 100 条。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。

    Returns:
        None。

    Raises:
        无业务异常。
    """
    overflow_ids = (
        select(PlayHistory.id)
        .where(PlayHistory.user_id == user_id)
        .order_by(desc(PlayHistory.played_at), desc(PlayHistory.id))
        .offset(MAX_PLAY_HISTORY_ITEMS)
        .subquery()
    )
    await db.execute(
        delete(PlayHistory)
        .where(PlayHistory.id.in_(select(overflow_ids.c.id)))
        .execution_options(synchronize_session=False)
    )


async def list_play_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """查询用户的播放历史。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 按播放时间倒序的 PlayHistory 列表, "total": 总记录数}。
    """
    where_clause = [PlayHistory.user_id == user_id]
    stmt = (
        select(PlayHistory)
        .where(*where_clause)
        .order_by(desc(PlayHistory.played_at), desc(PlayHistory.id))
        .options(
            selectinload(PlayHistory.music)
            .selectinload(Music.authors)
            .selectinload(MusicAuthor.author),
        )
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


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
        raise BusinessError("Play history record not found", code=ErrorCode.PLAY_HISTORY_NOT_FOUND)

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
