"""字典引用校验服务模块。

提供对情感标签、兴趣标签、乐器等字典表数据的批量存在性校验能力，
在业务层创建或更新关联实体前调用，防止出现外键引用不存在的字典项。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.models.dictionary import EmotionTag, InterestTag, Instrument


async def validate_emotion_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
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


async def validate_interest_tags_exist(db: AsyncSession, tag_ids: list[int]) -> None:
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


async def validate_instruments_exist(db: AsyncSession, instrument_ids: list[int]) -> None:
    """批量校验乐器 ID 是否存在。

    Args:
        db: SQLAlchemy 异步 Session。
        instrument_ids: 待校验的乐器 ID 列表。

    Returns:
        None。

    Raises:
        BusinessError: 存在不存在的乐器 ID 时抛出，状态码 404。
    """
    if not instrument_ids:
        return
    stmt = select(Instrument.id).where(Instrument.id.in_(instrument_ids))
    existing = {row for row in (await db.execute(stmt)).scalars()}
    missing = set(instrument_ids) - existing
    if missing:
        raise BusinessError(f"Instruments not found: {sorted(missing)}", 404)
