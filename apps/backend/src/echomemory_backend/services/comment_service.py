"""评论业务服务模块，提供评论的创建、查询、删除、点赞/点踩等核心操作。"""

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.db.pagination import paginate
from echomemory_backend.models.comment import Comment, CommentDislike, CommentLike
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.schemas.comment import CommentOut
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.services.cache_service import invalidate_music_detail
from echomemory_backend.services.notification_service import create_notification
from echomemory_backend.services.space_post_service import can_view_space_post


_VALID_TARGET_TYPES = ("music", "playlist", "space_post")


def _can_view_playlist(viewer_id: int | None, playlist: Playlist) -> bool:
    """判断查看者是否有权访问歌单（与歌单详情接口规则一致）。

    Args:
        viewer_id: 查看者用户主键，未登录时为 None。
        playlist: 歌单 ORM 实例。

    Returns:
        公开歌单或所有者查看自己的私密歌单时返回 True。
    """
    if not playlist.is_private:
        return True
    return viewer_id is not None and playlist.user_id == viewer_id


async def _validate_target_exists(
    db: AsyncSession, target_type: str, target_id: int, viewer_id: int | None = None
) -> None:
    """校验评论目标是否存在且可见。

    Args:
        db: SQLAlchemy 异步 Session。
        target_type: 目标类型（music / playlist / space_post）。
        target_id: 目标主键。
        viewer_id: 查看者用户主键，用于校验 space_post 的私密权限。

    Returns:
        None。

    Raises:
        BusinessError: 目标不存在或不可见时抛出 404。
    """
    if target_type == "music":
        target = await db.get(Music, target_id)
        if target is None or not target.is_published:
            raise BusinessError("Target not found", 404)
    elif target_type == "playlist":
        target = await db.get(Playlist, target_id)
        if target is None or not _can_view_playlist(viewer_id, target):
            raise BusinessError("Target not found", 404)
    elif target_type == "space_post":
        target = await db.get(SpacePost, target_id)
        if target is None or not can_view_space_post(viewer_id, target):
            raise BusinessError("Target not found", 404)


async def _resolve_parent(
    db: AsyncSession,
    parent_id: int | None,
    target_type: str,
    target_id: int,
) -> tuple[int | None, bool]:
    """根据 parent_id 解析 root_id 和 is_nested_reply。

    Args:
        db: SQLAlchemy 异步 Session。
        parent_id: 父评论 ID，无父评论时为 None。
        target_type: 目标类型（music / playlist / space_post）。
        target_id: 目标主键。

    Returns:
        (root_id, is_nested_reply) 元组。root_id 为根评论 ID 或 None，
        is_nested_reply 表示是否为嵌套回复。

    Raises:
        BusinessError: 父评论不存在或父评论不属于同一目标时抛出。
    """
    if parent_id is None:
        return None, False

    parent = await db.get(Comment, parent_id)
    if parent is None or parent.is_deleted:
        raise BusinessError("Parent comment not found", 404)

    # 校验 parent 是否属于同一个 target
    parent_target_match = {
        "music": parent.music_id == target_id,
        "playlist": parent.playlist_id == target_id,
        "space_post": parent.space_post_id == target_id,
    }[target_type]
    if not parent_target_match:
        raise BusinessError("Parent comment does not belong to the same target", 400)

    if parent.root_id is None:
        return parent.id, False
    return parent.root_id, True


async def _get_comment_with_user(db: AsyncSession, comment_id: int) -> Comment:
    """加载 user 关联后的单条评论。

    Args:
        db: SQLAlchemy 异步 Session。
        comment_id: 评论主键。

    Returns:
        关联加载用户信息的 Comment 实例。
    """
    stmt = (
        select(Comment)
        .where(Comment.id == comment_id)
        .options(selectinload(Comment.user))
    )
    return (await db.execute(stmt)).scalar_one()


async def create_comment(
    db: AsyncSession,
    *,
    user_id: int,
    target_type: str,
    target_id: int,
    content: str,
    parent_id: int | None = None,
) -> Comment:
    """发表评论（含回复）。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 评论作者主键。
        target_type: 目标类型（music / playlist / space_post）。
        target_id: 目标主键。
        content: 评论内容。
        parent_id: 父评论 ID，无父评论时默认为 None。

    Returns:
        创建后的 Comment 实例（已关联用户信息）。

    Raises:
        BusinessError: target_type 无效或目标不存在时抛出。
    """
    if target_type not in _VALID_TARGET_TYPES:
        raise BusinessError("Invalid target_type", 400)

    await _validate_target_exists(db, target_type, target_id, viewer_id=user_id)
    root_id, is_nested_reply = await _resolve_parent(db, parent_id, target_type, target_id)

    comment = Comment(
        user_id=user_id,
        content=content,
        music_id=target_id if target_type == "music" else None,
        playlist_id=target_id if target_type == "playlist" else None,
        space_post_id=target_id if target_type == "space_post" else None,
        parent_id=parent_id,
        root_id=root_id,
        is_nested_reply=is_nested_reply,
    )
    db.add(comment)
    await db.flush()

    # 维护目标实体或父评论的计数（原子 UPDATE）
    if parent_id is None:
        target_cls = {"music": Music, "playlist": Playlist, "space_post": SpacePost}[
            target_type
        ]
        await db.execute(
            update(target_cls)
            .where(target_cls.id == target_id)
            .values(comment_count=target_cls.comment_count + 1)
        )
    else:
        await db.execute(
            update(Comment)
            .where(Comment.id == parent_id)
            .values(reply_count=Comment.reply_count + 1)
        )

    comment_id = comment.id

    # 通知触发：评论被回复 / 空间动态被评论（与业务操作同一事务提交）
    if parent_id is not None:
        parent = await db.get(Comment, parent_id)
        if parent is not None and not parent.is_deleted:
            await create_notification(
                db,
                recipient_id=parent.user_id,
                actor_id=user_id,
                type=NotificationType.COMMENT_REPLY,
                target_type="comment",
                target_id=parent_id,
                extra={"reply_comment_id": comment_id, "content": content[:100]},
            )
    elif target_type == "space_post":
        space_post = await db.get(SpacePost, target_id)
        if space_post is not None and not space_post.is_deleted:
            await create_notification(
                db,
                recipient_id=space_post.user_id,
                actor_id=user_id,
                type=NotificationType.SPACE_POST_COMMENT,
                target_type="space_post",
                target_id=target_id,
                extra={"comment_id": comment_id, "content": content[:100]},
            )

    # 仅 music 类型评论触发热度重算
    if target_type == "music":
        from echomemory_backend.services.hotness_service import recalculate_music_hot

        await recalculate_music_hot(db, target_id)

    await db.commit()

    # 在事务提交后失效音乐详情缓存，避免并发场景下旧数据被重新写回缓存
    if target_type == "music":
        await invalidate_music_detail(target_id)

    return await _get_comment_with_user(db, comment_id)


async def list_comments(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    viewer_user_id: int | None = None,
    sort_by: str = "recommended",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """查询指定目标的 root 评论列表。

    Args:
        db: SQLAlchemy 异步 Session。
        target_type: 目标类型（music / playlist / space_post）。
        target_id: 目标主键。
        viewer_user_id: 查看者用户主键，用于校验 space_post 的私密权限。
        sort_by: 排序方式：recommended（综合=精选优先→最新）、latest（最新）、likes（点赞最多）。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 排除已删除的 Comment 列表, "total": 总记录数}。

    Raises:
        BusinessError: target_type 无效或目标不可见时抛出 400/404。
    """
    if target_type not in _VALID_TARGET_TYPES:
        raise BusinessError("Invalid target_type", 400)

    if target_type == "playlist":
        target = await db.get(Playlist, target_id)
        if target is None or not _can_view_playlist(viewer_user_id, target):
            raise BusinessError("Target not found", 404)
    elif target_type == "space_post":
        target = await db.get(SpacePost, target_id)
        if target is None or not can_view_space_post(viewer_user_id, target):
            raise BusinessError("Target not found", 404)

    target_filter = {
        "music": Comment.music_id == target_id,
        "playlist": Comment.playlist_id == target_id,
        "space_post": Comment.space_post_id == target_id,
    }[target_type]

    where_clause = [
        target_filter,
        Comment.parent_id.is_(None),
        Comment.is_deleted.is_(False),
    ]

    _COMMENT_SORT = {
        "recommended": [desc(Comment.is_recommended), desc(Comment.created_at)],
        "latest": [desc(Comment.created_at)],
        "likes": [desc(Comment.like_count), desc(Comment.created_at)],
    }
    sort_columns = _COMMENT_SORT.get(sort_by, _COMMENT_SORT["recommended"])

    stmt = (
        select(Comment)
        .where(*where_clause)
        .order_by(*sort_columns)
        .options(selectinload(Comment.user))
    )
    page = await paginate(db, stmt, where_clause, limit=limit, offset=offset)
    return {"items": page.items, "total": page.total}


async def list_replies(
    db: AsyncSession,
    root_id: int,
) -> list[Comment]:
    """获取指定根评论的所有非删除回复（按创建时间正序）。

    Args:
        db: SQLAlchemy 异步 Session。
        root_id: 根评论主键。

    Returns:
        回复 Comment 列表（已关联用户信息）。
    """
    stmt = (
        select(Comment)
        .where(
            Comment.root_id == root_id,
            Comment.is_deleted.is_(False),
        )
        .order_by(Comment.created_at)
        .options(selectinload(Comment.user))
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """软删除评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 操作者主键。
        comment_id: 评论主键。

    Returns:
        None。

    Raises:
        BusinessError: 评论不存在时抛出 404，非作者操作时抛出 403。
    """
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)
    if comment.user_id != user_id:
        raise BusinessError("Permission denied", 403)

    comment.is_deleted = True

    # 维护目标实体或父评论的计数（原子 UPDATE + 防负保护）
    if comment.parent_id is None:
        if comment.music_id is not None:
            await db.execute(
                update(Music)
                .where(Music.id == comment.music_id, Music.comment_count > 0)
                .values(comment_count=Music.comment_count - 1)
            )
        elif comment.playlist_id is not None:
            await db.execute(
                update(Playlist)
                .where(Playlist.id == comment.playlist_id, Playlist.comment_count > 0)
                .values(comment_count=Playlist.comment_count - 1)
            )
        elif comment.space_post_id is not None:
            await db.execute(
                update(SpacePost)
                .where(
                    SpacePost.id == comment.space_post_id,
                    SpacePost.comment_count > 0,
                )
                .values(comment_count=SpacePost.comment_count - 1)
            )
    else:
        await db.execute(
            update(Comment)
            .where(Comment.id == comment.parent_id, Comment.reply_count > 0)
            .values(reply_count=Comment.reply_count - 1)
        )

    await db.commit()


async def like_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """点赞评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        comment_id: 评论主键。

    Returns:
        None。

    Raises:
        BusinessError: 评论不存在时抛出 404。
    """
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)

    existing = await db.get(CommentLike, (comment_id, user_id))
    if existing is not None:
        return

    db.add(CommentLike(comment_id=comment_id, user_id=user_id))
    await db.execute(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(like_count=Comment.like_count + 1)
    )
    # 维护评论作者的 like_count
    from echomemory_backend.models.user import User
    await db.execute(
        update(User)
        .where(User.id == comment.user_id)
        .values(like_count=User.like_count + 1)
    )

    if comment.user_id != user_id:
        await create_notification(
            db,
            recipient_id=comment.user_id,
            actor_id=user_id,
            type=NotificationType.COMMENT_LIKE,
            target_type="comment",
            target_id=comment_id,
            extra={"content": comment.content[:100]},
        )

    await db.commit()


async def unlike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """取消点赞评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        comment_id: 评论主键。

    Returns:
        None。
    """
    existing = await db.get(CommentLike, (comment_id, user_id))
    if existing is not None:
        await db.delete(existing)
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.like_count > 0)
            .values(like_count=Comment.like_count - 1)
        )
        # 维护评论作者的 like_count（防负保护）
        comment = await db.get(Comment, comment_id)
        if comment is not None:
            from echomemory_backend.models.user import User
            await db.execute(
                update(User)
                .where(User.id == comment.user_id, User.like_count > 0)
                .values(like_count=User.like_count - 1)
            )
        await db.commit()


async def dislike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """点踩评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        comment_id: 评论主键。

    Returns:
        None。

    Raises:
        BusinessError: 评论不存在时抛出 404。
    """
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)

    existing = await db.get(CommentDislike, (comment_id, user_id))
    if existing is not None:
        return

    db.add(CommentDislike(comment_id=comment_id, user_id=user_id))
    await db.execute(
        update(Comment)
        .where(Comment.id == comment_id)
        .values(dislike_count=Comment.dislike_count + 1)
    )
    await db.commit()


async def undislike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """取消点踩评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        comment_id: 评论主键。

    Returns:
        None。
    """
    existing = await db.get(CommentDislike, (comment_id, user_id))
    if existing is not None:
        await db.delete(existing)
        await db.execute(
            update(Comment)
            .where(Comment.id == comment_id, Comment.dislike_count > 0)
            .values(dislike_count=Comment.dislike_count - 1)
        )
        await db.commit()


async def _get_user_comment_reactions(
    db: AsyncSession,
    viewer_user_id: int | None,
    comment_ids: list[int],
) -> tuple[set[int], set[int]]:
    """批量查询当前用户对评论的点赞/点踩状态。

    Args:
        db: SQLAlchemy 异步 Session。
        viewer_user_id: 查看者主键，未登录时为 None。
        comment_ids: 评论主键列表。

    Returns:
        (已点赞评论 ID 集合, 已点踩评论 ID 集合)。
    """
    if viewer_user_id is None or not comment_ids:
        return set(), set()
    liked_result = await db.execute(
        select(CommentLike.comment_id).where(
            CommentLike.user_id == viewer_user_id,
            CommentLike.comment_id.in_(comment_ids),
        )
    )
    disliked_result = await db.execute(
        select(CommentDislike.comment_id).where(
            CommentDislike.user_id == viewer_user_id,
            CommentDislike.comment_id.in_(comment_ids),
        )
    )
    return set(liked_result.scalars().all()), set(disliked_result.scalars().all())


def build_comment_out(
    comment: Comment,
    liked_ids: set[int],
    disliked_ids: set[int],
) -> CommentOut:
    """将评论 ORM 实例转换为带互动状态的 CommentOut。

    Args:
        comment: 评论 ORM 实例。
        liked_ids: 当前用户已点赞的评论 ID 集合。
        disliked_ids: 当前用户已点踩的评论 ID 集合。

    Returns:
        包含 liked_by_me / disliked_by_me 的 CommentOut。
    """
    return CommentOut.model_validate(comment).model_copy(
        update={
            "liked_by_me": comment.id in liked_ids,
            "disliked_by_me": comment.id in disliked_ids,
        }
    )


async def build_comment_outs(
    db: AsyncSession,
    comments: list[Comment],
    viewer_user_id: int | None,
) -> list[CommentOut]:
    """批量构建带互动状态的评论输出列表。

    Args:
        db: SQLAlchemy 异步 Session。
        comments: 评论 ORM 列表。
        viewer_user_id: 查看者主键，未登录时为 None。

    Returns:
        CommentOut 列表。
    """
    comment_ids = [c.id for c in comments]
    liked_ids, disliked_ids = await _get_user_comment_reactions(
        db, viewer_user_id, comment_ids
    )
    return [
        build_comment_out(comment, liked_ids, disliked_ids) for comment in comments
    ]
