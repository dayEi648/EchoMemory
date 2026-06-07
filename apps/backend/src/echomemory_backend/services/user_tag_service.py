from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.user_tag import UserEmotionTag, UserInterestTag


async def list_user_emotion_tags(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的情感标签列表，按绑定时间倒序。"""
    result = await db.execute(
        select(UserEmotionTag)
        .where(UserEmotionTag.user_id == user_id)
        .options(selectinload(UserEmotionTag.emotion_tag))
        .order_by(desc(UserEmotionTag.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.emotion_tag_id,
            "name": item.emotion_tag.name,
            "created_at": item.created_at,
        }
        for item in items
    ]


async def list_user_interest_tags(db: AsyncSession, user_id: int) -> list[dict]:
    """查询指定用户的兴趣标签列表，按绑定时间倒序。"""
    result = await db.execute(
        select(UserInterestTag)
        .where(UserInterestTag.user_id == user_id)
        .options(selectinload(UserInterestTag.interest_tag))
        .order_by(desc(UserInterestTag.created_at))
    )
    items = result.scalars().all()
    return [
        {
            "tag_id": item.interest_tag_id,
            "name": item.interest_tag.name,
            "created_at": item.created_at,
        }
        for item in items
    ]
