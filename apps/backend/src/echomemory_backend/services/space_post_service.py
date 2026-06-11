"""空间动态（SpacePost）业务服务模块，提供动态的创建、查询、列表、删除及点赞等功能。"""

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.space_post import SpacePost, SpacePostImage, SpacePostLike
from echomemory_backend.core.exceptions import BusinessError


async def create_space_post(
    db: AsyncSession,
    user_id: int,
    content: str | None,
    is_private: bool,
    image_urls: list[str],
) -> SpacePost:
    """创建空间动态及关联图片。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 发布者主键。
        content: 动态文本内容。
        is_private: 是否为私密动态。
        image_urls: 图片 URL 列表。

    Returns:
        创建后的 SpacePost 实例。
    """
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
    """根据 ID 获取动态详情。

    Args:
        db: SQLAlchemy 异步 Session。
        post_id: 动态主键。

    Returns:
        包含图片关联的 SpacePost 实例，不存在时返回 None。
    """
    result = await db.execute(
        select(SpacePost)
        .where(SpacePost.id == post_id)
        .options(selectinload(SpacePost.images))
    )
    return result.scalar_one_or_none()


def can_view_space_post(viewer_id: int | None, post: SpacePost) -> bool:
    """判断 viewer 是否有权查看该空间动态。

    已删除动态对任何人都不可见。
    私密动态仅作者本人可见。
    公开动态对所有人可见。

    Args:
        viewer_id: 查看者用户主键，未登录时为 None。
        post: 空间动态实例。

    Returns:
        有权查看返回 True，否则返回 False。
    """
    if post.is_deleted:
        return False
    if post.is_private and post.user_id != viewer_id:
        return False
    return True


async def list_space_posts(
    db: AsyncSession,
    target_user_id: int,
    viewer_user_id: int,
    limit: int,
    offset: int,
) -> dict[str, object]:
    """列出目标用户的动态。

    Args:
        db: SQLAlchemy 异步 Session。
        target_user_id: 目标用户主键。
        viewer_user_id: 查看者主键。
        limit: 返回数量上限。
        offset: 偏移量。

    Returns:
        {"items": SpacePost 列表, "total": 总记录数}。
    """
    where_clause = [
        SpacePost.user_id == target_user_id,
        SpacePost.is_deleted == False,
    ]
    if target_user_id != viewer_user_id:
        where_clause.append(SpacePost.is_private == False)

    stmt = (
        select(SpacePost)
        .where(*where_clause)
        .options(selectinload(SpacePost.images))
        .order_by(desc(SpacePost.created_at))
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}


async def soft_delete_space_post(db: AsyncSession, post: SpacePost) -> None:
    """软删除动态。

    Args:
        db: SQLAlchemy 异步 Session。
        post: 要软删除的 SpacePost 实例。

    Returns:
        None。
    """
    post.is_deleted = True
    await db.commit()


async def hard_delete_space_post(db: AsyncSession, post_id: int) -> list[str]:
    """硬删除动态及其关联记录。

    Args:
        db: SQLAlchemy 异步 Session。
        post_id: 动态主键。

    Returns:
        待清理的图片 URL 列表。

    Raises:
        BusinessError: 动态不存在时抛出 404。
    """
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
    """点赞动态（幂等）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        post_id: 动态主键。

    Returns:
        None。
    """
    existing = await db.get(SpacePostLike, (post_id, user_id))
    if existing is not None:
        return

    like = SpacePostLike(post_id=post_id, user_id=user_id)
    db.add(like)
    await db.commit()


async def unlike_space_post(db: AsyncSession, user_id: int, post_id: int) -> None:
    """取消点赞动态（幂等）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        post_id: 动态主键。

    Returns:
        None。
    """
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
