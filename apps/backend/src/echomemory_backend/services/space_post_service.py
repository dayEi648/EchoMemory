"""空间动态（SpacePost）业务服务模块，提供动态的创建、查询、列表、删除及点赞等功能。"""
from echomemory_backend.core.exceptions.codes import ErrorCode

from sqlalchemy import desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.db.pagination import paginate
from echomemory_backend.models.album import Album
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost, SpacePostImage, SpacePostLike
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.schemas.space_post import SpacePostListOut, SpacePostOut
from echomemory_backend.services.notification_service import create_notification


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
    from echomemory_backend.services.content_moderation_service import (
        enqueue_moderation,
    )

    await enqueue_moderation(
        db,
        content_type="space_post",
        content_id=post.id,
    )
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

    用户主动删除的动态对任何人都不可见。
    审核删除的动态保留可见（前端渲染占位提示）。
    私密动态仅作者本人可见。
    公开动态对所有人可见。

    Args:
        viewer_id: 查看者用户主键，未登录时为 None。
        post: 空间动态实例。

    Returns:
        有权查看返回 True，否则返回 False。
    """
    if post.is_deleted and post.deletion_reason == "USER":
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
    # 仅过滤用户主动删除的动态；审核删除的动态保留（前端渲染占位提示）
    where_clause = [
        SpacePost.user_id == target_user_id,
        or_(
            SpacePost.is_deleted == False,
            SpacePost.deletion_reason != "USER",
        ),
    ]
    if target_user_id != viewer_user_id:
        where_clause.append(SpacePost.is_private == False)

    stmt = (
        select(SpacePost)
        .where(*where_clause)
        .options(selectinload(SpacePost.images))
        .order_by(desc(SpacePost.created_at))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def soft_delete_space_post(
    db: AsyncSession, *, user_id: int, post: SpacePost
) -> None:
    """软删除动态。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 操作者主键，须为动态作者。
        post: 要软删除的 SpacePost 实例。

    Returns:
        None。

    Raises:
        BusinessError: 非作者操作时抛出 403。
    """
    if post.user_id != user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)
    post.is_deleted = True
    post.deletion_reason = "USER"
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
        raise BusinessError("Post not found", code=ErrorCode.SPACE_POST_NOT_FOUND)

    image_urls = [img.image_url for img in post.images]

    # 手动删除关联记录（避免复合主键级联冲突）
    for img in post.images:
        await db.delete(img)

    likes_result = await db.execute(
        select(SpacePostLike).where(SpacePostLike.post_id == post_id)
    )
    likes = list(likes_result.scalars().all())
    like_count = len(likes)
    if like_count > 0:
        from echomemory_backend.models.user import User

        await db.execute(
            update(User)
            .where(User.id == post.user_id, User.like_count >= like_count)
            .values(like_count=User.like_count - like_count)
        )
    for like in likes:
        await db.delete(like)

    await db.delete(post)
    await db.commit()
    return image_urls


_VALID_FORWARD_TYPES = ("space_post", "music", "album", "playlist")


async def forward_to_space(
    db: AsyncSession,
    user_id: int,
    *,
    source_type: str,
    source_id: int,
    content: str | None = None,
) -> SpacePost:
    """转发内容到自己的空间动态。

    支持的 source_type：space_post / music / album / playlist。
    转发时递增源实体的 forward_count。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 转发者主键。
        source_type: 源实体类型。
        source_id: 源实体主键。
        content: 转发附言，可选。

    Returns:
        创建后的 SpacePost 实例。

    Raises:
        BusinessError: source_type 非法或源实体不存在/不可访问时抛出。
    """
    if source_type not in _VALID_FORWARD_TYPES:
        raise BusinessError(f"Invalid source_type: {source_type}", code=ErrorCode.CLIENT_INVALID_SOURCE_TYPE)

    # 校验源实体存在且可访问
    source_title = ""
    if source_type == "space_post":
        source_post = await db.get(SpacePost, source_id)
        if source_post is None or source_post.is_deleted or source_post.is_private:
            raise BusinessError("Source post not found or not accessible", code=ErrorCode.SPACE_POST_SOURCE_NOT_FOUND)
        source_title = source_post.content or ""
        await db.execute(
            update(SpacePost)
            .where(SpacePost.id == source_id)
            .values(forward_count=SpacePost.forward_count + 1)
        )
    elif source_type == "music":
        music = await db.get(Music, source_id)
        if music is None or not music.is_published:
            raise BusinessError("Music not found", code=ErrorCode.MUSIC_NOT_FOUND)
        source_title = music.title
        await db.execute(
            update(Music)
            .where(Music.id == source_id)
            .values(forward_count=Music.forward_count + 1)
        )
    elif source_type == "album":
        album = await db.get(Album, source_id)
        if album is None or album.is_deleted:
            raise BusinessError("Album not found", code=ErrorCode.ALBUM_NOT_FOUND)
        source_title = album.title
        await db.execute(
            update(Album)
            .where(Album.id == source_id)
            .values(forward_count=Album.forward_count + 1)
        )
    elif source_type == "playlist":
        playlist = await db.get(Playlist, source_id)
        if playlist is None or playlist.is_private:
            raise BusinessError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND)
        source_title = playlist.title
        await db.execute(
            update(Playlist)
            .where(Playlist.id == source_id)
            .values(forward_count=Playlist.forward_count + 1)
        )

    post = SpacePost(
        user_id=user_id,
        content=content or None,
        is_private=False,
        post_type="forward",
        source_id=source_id,
        source_type=source_type,
        extra={"source_title": source_title[:100]} if source_title else {},
    )
    db.add(post)
    await db.flush()
    from echomemory_backend.services.content_moderation_service import (
        enqueue_moderation,
    )

    await enqueue_moderation(
        db,
        content_type="space_post",
        content_id=post.id,
    )
    await db.commit()
    await db.refresh(post)
    return post


async def like_space_post(db: AsyncSession, user_id: int, post_id: int) -> None:
    """点赞动态（幂等）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        post_id: 动态主键。

    Returns:
        None。

    Raises:
        BusinessError: 动态不存在、不可见或不能自赞时抛出 404/403。
    """
    post = await db.get(SpacePost, post_id)
    if post is None or post.is_deleted or not can_view_space_post(user_id, post):
        raise BusinessError("Post not found", code=ErrorCode.SPACE_POST_NOT_FOUND)
    if post.user_id == user_id:
        raise BusinessError("Cannot like your own post", code=ErrorCode.PERMISSION_DENIED)

    existing = await db.get(SpacePostLike, (post_id, user_id))
    if existing is not None:
        return

    db.add(SpacePostLike(post_id=post_id, user_id=user_id))

    from echomemory_backend.models.user import User
    await db.execute(
        update(User)
        .where(User.id == post.user_id)
        .values(like_count=User.like_count + 1)
    )

    await create_notification(
        db,
        recipient_id=post.user_id,
        actor_id=user_id,
        type=NotificationType.SPACE_POST_LIKE,
        target_type="space_post",
        target_id=post_id,
        extra={"content": (post.content or "")[:100]},
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


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
        # 维护动态作者的 like_count（防负保护）
        post = await db.get(SpacePost, post_id)
        if post is not None:
            from echomemory_backend.models.user import User
            await db.execute(
                update(User)
                .where(User.id == post.user_id, User.like_count > 0)
                .values(like_count=User.like_count - 1)
            )
        await db.commit()


async def _get_post_like_counts(
    db: AsyncSession, post_ids: list[int]
) -> dict[int, int]:
    """批量查询动态的点赞数。

    Args:
        db: SQLAlchemy 异步 Session。
        post_ids: 动态主键列表。

    Returns:
        post_id 到点赞数的映射。
    """
    if not post_ids:
        return {}
    result = await db.execute(
        select(SpacePostLike.post_id, func.count())
        .where(SpacePostLike.post_id.in_(post_ids))
        .group_by(SpacePostLike.post_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def _get_user_liked_post_ids(
    db: AsyncSession, user_id: int, post_ids: list[int]
) -> set[int]:
    """批量查询用户已点赞的动态 ID 集合。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        post_ids: 动态主键列表。

    Returns:
        用户已点赞的 post_id 集合。
    """
    if not post_ids:
        return set()
    result = await db.execute(
        select(SpacePostLike.post_id).where(
            SpacePostLike.user_id == user_id,
            SpacePostLike.post_id.in_(post_ids),
        )
    )
    return set(result.scalars().all())


def build_space_post_out(
    post: SpacePost,
    like_count: int,
    liked_by_me: bool,
) -> SpacePostOut:
    """将动态 ORM 实例转换为带点赞状态的 SpacePostOut。

    Args:
        post: 动态 ORM 实例。
        like_count: 点赞数。
        liked_by_me: 当前用户是否已点赞。

    Returns:
        SpacePostOut 实例。
    """
    return SpacePostOut.model_validate(post).model_copy(
        update={"like_count": like_count, "liked_by_me": liked_by_me}
    )


def build_space_post_list_out(
    post: SpacePost,
    like_count: int,
    liked_by_me: bool,
) -> SpacePostListOut:
    """将动态 ORM 实例转换为带点赞状态的 SpacePostListOut。

    Args:
        post: 动态 ORM 实例。
        like_count: 点赞数。
        liked_by_me: 当前用户是否已点赞。

    Returns:
        SpacePostListOut 实例。
    """
    return SpacePostListOut.model_validate(post).model_copy(
        update={"like_count": like_count, "liked_by_me": liked_by_me}
    )


async def build_space_post_outs(
    db: AsyncSession,
    posts: list[SpacePost],
    viewer_user_id: int,
    *,
    as_list_item: bool = False,
) -> list[SpacePostOut | SpacePostListOut]:
    """批量构建带点赞状态的动态输出列表。

    Args:
        db: SQLAlchemy 异步 Session。
        posts: 动态 ORM 列表。
        viewer_user_id: 查看者主键。
        as_list_item: 为 True 时返回 SpacePostListOut，否则返回 SpacePostOut。

    Returns:
        动态输出列表。
    """
    post_ids = [p.id for p in posts]
    like_counts = await _get_post_like_counts(db, post_ids)
    liked_ids = await _get_user_liked_post_ids(db, viewer_user_id, post_ids)
    builder = build_space_post_list_out if as_list_item else build_space_post_out
    return [
        builder(
            post,
            like_counts.get(post.id, 0),
            post.id in liked_ids,
        )
        for post in posts
    ]
