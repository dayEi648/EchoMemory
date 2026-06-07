from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.space_post import SpacePost, SpacePostImage, SpacePostLike
from echomemory_backend.services.user_service import BusinessError


async def create_space_post(
    db: AsyncSession,
    user_id: int,
    content: str | None,
    is_private: bool,
    image_urls: list[str],
) -> SpacePost:
    """创建空间动态及关联图片。"""
    post = SpacePost(
        user_id=user_id,
        content=content,
        is_private=is_private,
        post_type="original",
    )
    db.add(post)
    await db.flush()
    for idx, url in enumerate(image_urls):
        db.add(SpacePostImage(post_id=post.id, image_url=url, ordinal=idx))
    await db.commit()
    await db.refresh(post)
    return post


async def get_space_post_by_id(db: AsyncSession, post_id: int) -> SpacePost | None:
    """根据 ID 获取动态详情（含图片）。"""
    result = await db.execute(
        select(SpacePost)
        .where(SpacePost.id == post_id)
        .options(selectinload(SpacePost.images))
    )
    return result.scalar_one_or_none()


async def list_space_posts(
    db: AsyncSession,
    target_user_id: int,
    viewer_user_id: int,
    limit: int,
    offset: int,
) -> list[SpacePost]:
    """列出目标用户的动态。排除已删除；非本人时排除 private。按 created_at 倒序。"""
    stmt = (
        select(SpacePost)
        .where(SpacePost.user_id == target_user_id)
        .where(SpacePost.is_deleted == False)
        .options(selectinload(SpacePost.images))
        .order_by(desc(SpacePost.created_at))
        .limit(limit)
        .offset(offset)
    )
    if target_user_id != viewer_user_id:
        stmt = stmt.where(SpacePost.is_private == False)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def soft_delete_space_post(db: AsyncSession, post: SpacePost) -> None:
    """软删除动态。"""
    post.is_deleted = True
    await db.commit()


async def hard_delete_space_post(db: AsyncSession, post_id: int) -> list[str]:
    """硬删除动态及其关联记录。返回待清理的图片 URL 列表。"""
    post = await get_space_post_by_id(db, post_id)
    if post is None:
        raise BusinessError("Post not found", 404)

    image_urls = [img.image_url for img in post.images]

    # 手动删除关联记录（避免复合主键级联冲突）
    for img in post.images:
        await db.delete(img)

    likes_result = await db.execute(
        select(SpacePostLike).where(SpacePostLike.post_id == post_id)
    )
    for like in likes_result.scalars().all():
        await db.delete(like)

    await db.delete(post)
    await db.commit()
    return image_urls


async def like_space_post(db: AsyncSession, user_id: int, post_id: int) -> None:
    """点赞动态（幂等）。"""
    like = SpacePostLike(post_id=post_id, user_id=user_id)
    db.add(like)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


async def unlike_space_post(db: AsyncSession, user_id: int, post_id: int) -> None:
    """取消点赞（幂等）。"""
    result = await db.execute(
        select(SpacePostLike).where(
            SpacePostLike.post_id == post_id,
            SpacePostLike.user_id == user_id,
        )
    )
    like = result.scalar_one_or_none()
    if like is not None:
        await db.delete(like)
        await db.commit()
