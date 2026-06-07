from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.music import Music
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.services.user_service import BusinessError


async def create_play_history(
    db: AsyncSession, user_id: int, music_id: int
) -> PlayHistory:
    """创建一条播放历史记录。

    校验音乐存在且已上架，否则抛出 BusinessError(404)。
    """
    music = await db.get(Music, music_id)
    if music is None or not music.is_published:
        raise BusinessError("Music not found", 404)

    history = PlayHistory(user_id=user_id, music_id=music_id)
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


async def list_play_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[PlayHistory]:
    """查询用户的播放历史，按播放时间倒序，关联加载音乐信息。"""
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

    若记录不存在或不属于该用户，抛出 BusinessError(404)。
    """
    history = await db.get(PlayHistory, history_id)
    if history is None or history.user_id != user_id:
        raise BusinessError("Play history record not found", 404)

    await db.delete(history)
    await db.commit()


async def clear_play_history(db: AsyncSession, user_id: int) -> None:
    """清空该用户的全部播放历史。"""
    await db.execute(
        delete(PlayHistory).where(PlayHistory.user_id == user_id)
    )
    await db.commit()
