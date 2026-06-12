"""多对多关联重建辅助模块。"""

from collections.abc import Awaitable, Callable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.music import MusicEmotionTag, MusicInterestTag


async def rebuild_tag_association(
    db: AsyncSession,
    *,
    owner_id: int,
    owner_fk: str,
    tag_ids: list[int],
    assoc_model: type,
    tag_fk: str,
    validate_fn: Callable[[AsyncSession, list[int]], Awaitable[None]],
) -> None:
    """覆盖式重建多对多标签/乐器关联：先校验存在性，再全量替换。

    Args:
        db: SQLAlchemy 异步 Session。
        owner_id: 宿主实体主键（如 music_id、album_id）。
        owner_fk: 关联表中的宿主外键字段名。
        tag_ids: 标签或乐器 ID 列表。
        assoc_model: 关联表 ORM 模型类。
        tag_fk: 关联表中的标签/乐器外键字段名。
        validate_fn: 批量存在性校验函数。

    Returns:
        None。

    Raises:
        BusinessError: validate_fn 发现缺失 ID 时抛出。
    """
    await validate_fn(db, tag_ids)
    owner_col = getattr(assoc_model, owner_fk)
    await db.execute(delete(assoc_model).where(owner_col == owner_id))
    for tag_id in tag_ids:
        db.add(assoc_model(**{owner_fk: owner_id, tag_fk: tag_id}))


async def sync_owner_tags_from_musics(
    db: AsyncSession,
    owner_id: int,
    *,
    music_join_model: type,
    owner_fk: str,
    emotion_assoc_model: type,
    interest_assoc_model: type,
) -> None:
    """根据容器内所有歌曲的标签并集，重建宿主的情感标签与兴趣标签。

    Args:
        db: SQLAlchemy 异步 Session。
        owner_id: 宿主实体主键（专辑或歌单 ID）。
        music_join_model: 宿主与歌曲的关联表模型（AlbumMusic 或 PlaylistMusic）。
        owner_fk: 关联表中的宿主外键字段名（album_id 或 playlist_id）。
        emotion_assoc_model: 宿主情感标签关联表模型。
        interest_assoc_model: 宿主兴趣标签关联表模型。

    Returns:
        None。
    """
    join_owner_col = getattr(music_join_model, owner_fk)
    emotion_owner_col = getattr(emotion_assoc_model, owner_fk)
    interest_owner_col = getattr(interest_assoc_model, owner_fk)

    emotion_stmt = (
        select(MusicEmotionTag.emotion_tag_id)
        .join(music_join_model, music_join_model.music_id == MusicEmotionTag.music_id)
        .where(join_owner_col == owner_id)
        .distinct()
    )
    emotion_tag_ids = list((await db.execute(emotion_stmt)).scalars().all())

    interest_stmt = (
        select(MusicInterestTag.interest_tag_id)
        .join(music_join_model, music_join_model.music_id == MusicInterestTag.music_id)
        .where(join_owner_col == owner_id)
        .distinct()
    )
    interest_tag_ids = list((await db.execute(interest_stmt)).scalars().all())

    await db.execute(
        delete(emotion_assoc_model).where(emotion_owner_col == owner_id)
    )
    for tag_id in emotion_tag_ids:
        db.add(emotion_assoc_model(**{owner_fk: owner_id, "emotion_tag_id": tag_id}))

    await db.execute(
        delete(interest_assoc_model).where(interest_owner_col == owner_id)
    )
    for tag_id in interest_tag_ids:
        db.add(interest_assoc_model(**{owner_fk: owner_id, "interest_tag_id": tag_id}))
