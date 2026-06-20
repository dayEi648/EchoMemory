"""评论业务服务模块，提供评论的创建、查询、删除、点赞/点踩等核心操作。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from echomemory_backend.db.pagination import paginate
from echomemory_backend.models.comment import Comment, CommentDislike, CommentLike
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.schemas.comment import CommentOut, CommentUserOut
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.services.cache_service import (
    invalidate_music_detail,
    invalidate_playlist_detail,
)
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
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)
    elif target_type == "playlist":
        target = await db.get(Playlist, target_id)
        if target is None or not _can_view_playlist(viewer_id, target):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)
    elif target_type == "space_post":
        target = await db.get(SpacePost, target_id)
        if target is None or not can_view_space_post(viewer_id, target):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)


async def _validate_comment_target_visible(
    db: AsyncSession, comment: Comment, viewer_id: int
) -> None:
    """校验评论所属目标对查看者可见。

    Args:
        db: SQLAlchemy 异步 Session。
        comment: 评论 ORM 实例。
        viewer_id: 查看者用户主键。

    Returns:
        None。

    Raises:
        BusinessError: 目标不存在或不可见时抛出 404。
    """
    if comment.music_id is not None:
        music = await db.get(Music, comment.music_id)
        if music is None or not music.is_published:
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)
    elif comment.playlist_id is not None:
        playlist = await db.get(Playlist, comment.playlist_id)
        if playlist is None or not _can_view_playlist(viewer_id, playlist):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)
    elif comment.space_post_id is not None:
        space_post = await db.get(SpacePost, comment.space_post_id)
        if space_post is None or not can_view_space_post(viewer_id, space_post):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)


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
        raise BusinessError("Parent comment not found", code=ErrorCode.COMMENT_PARENT_NOT_FOUND)

    # 校验 parent 是否属于同一个 target
    parent_target_match = {
        "music": parent.music_id == target_id,
        "playlist": parent.playlist_id == target_id,
        "space_post": parent.space_post_id == target_id,
    }[target_type]
    if not parent_target_match:
        raise BusinessError("Parent comment does not belong to the same target", code=ErrorCode.COMMENT_PARENT_TARGET_MISMATCH)

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
        raise BusinessError("Invalid target_type", code=ErrorCode.CLIENT_INVALID_TARGET_TYPE)

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

    # 维护目标实体的评论计数：所有评论（根评论、回复、嵌套回复）均计入
    target_cls = {"music": Music, "playlist": Playlist, "space_post": SpacePost}[
        target_type
    ]
    await db.execute(
        update(target_cls)
        .where(target_cls.id == target_id)
        .values(comment_count=target_cls.comment_count + 1)
    )

    # 维护父评论的回复计数（仅统计直接子回复）
    if parent_id is not None:
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

    # 在事务提交后失效相关详情缓存，避免并发场景下旧数据被重新写回缓存
    if target_type == "music":
        await invalidate_music_detail(target_id)
    elif target_type == "playlist":
        await invalidate_playlist_detail(target_id)

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
        raise BusinessError("Invalid target_type", code=ErrorCode.CLIENT_INVALID_TARGET_TYPE)

    if target_type == "playlist":
        target = await db.get(Playlist, target_id)
        if target is None or not _can_view_playlist(viewer_user_id, target):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)
    elif target_type == "space_post":
        target = await db.get(SpacePost, target_id)
        if target is None or not can_view_space_post(viewer_user_id, target):
            raise BusinessError("Target not found", code=ErrorCode.COMMENT_TARGET_NOT_FOUND)

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
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    """获取指定根评论的非删除回复（按创建时间正序，分页）。

    若根评论已软删除，则不返回任何回复。

    Args:
        db: SQLAlchemy 异步 Session。
        root_id: 根评论主键。
        limit: 返回数量上限，默认 20。
        offset: 偏移量，默认 0。

    Returns:
        {"items": 回复 Comment 列表, "total": 总记录数}。
    """
    root = aliased(Comment)
    where_clause = [
        Comment.root_id == root_id,
        Comment.is_deleted.is_(False),
        root.is_deleted.is_(False),
    ]
    stmt = (
        select(Comment)
        .join(root, Comment.root_id == root.id)
        .where(*where_clause)
        .order_by(Comment.created_at)
        .options(selectinload(Comment.user))
    )
    items = list(
        (await db.execute(stmt.limit(limit).offset(offset))).scalars().all()
    )
    count_stmt = (
        select(func.count())
        .select_from(Comment)
        .join(root, Comment.root_id == root.id)
        .where(*where_clause)
    )
    total = (await db.execute(count_stmt)).scalar_one()
    return {"items": items, "total": total}


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
        raise BusinessError("Comment not found", code=ErrorCode.COMMENT_NOT_FOUND)
    if comment.user_id != user_id:
        raise BusinessError("Permission denied", code=ErrorCode.PERMISSION_DENIED)

    comment.is_deleted = True

    # 确定评论所属目标类型与主键
    if comment.music_id is not None:
        target_type, target_id = "music", comment.music_id
    elif comment.playlist_id is not None:
        target_type, target_id = "playlist", comment.playlist_id
    elif comment.space_post_id is not None:
        target_type, target_id = "space_post", comment.space_post_id
    else:
        # 数据一致性兜底，理论上不会发生
        target_type, target_id = None, None

    # 清理点赞记录并扣减作者 like_count
    likes_result = await db.execute(
        select(CommentLike).where(CommentLike.comment_id == comment_id)
    )
    likes = list(likes_result.scalars().all())
    if likes:
        for like in likes:
            await db.delete(like)
        from echomemory_backend.models.user import User

        await db.execute(
            update(User)
            .where(
                User.id == comment.user_id,
                User.like_count >= len(likes),
            )
            .values(like_count=User.like_count - len(likes))
        )
        comment.like_count = max(0, comment.like_count - len(likes))

    # 维护目标实体的评论计数（原子 UPDATE + 防负保护）
    if target_type is None:
        target_cls = None
    else:
        target_cls = {
            "music": Music,
            "playlist": Playlist,
            "space_post": SpacePost,
        }[target_type]
    if target_cls is not None and comment.parent_id is None:
        # 根评论删除：其下所有可见回复也一并从目标计数中移除
        descendants_count = (
            await db.execute(
                select(func.count())
                .select_from(Comment)
                .where(
                    Comment.root_id == comment.id,
                    Comment.is_deleted.is_(False),
                )
            )
        ).scalar_one()
        total_to_remove = 1 + descendants_count
        await db.execute(
            update(target_cls)
            .where(
                target_cls.id == target_id,
                target_cls.comment_count >= total_to_remove,
            )
            .values(comment_count=target_cls.comment_count - total_to_remove)
        )
    elif target_cls is not None:
        # 非根评论删除：仅当其所属根评论未删除时才扣减目标计数
        root = (
            await db.get(Comment, comment.root_id)
            if comment.root_id is not None
            else None
        )
        if root is not None and not root.is_deleted:
            await db.execute(
                update(target_cls)
                .where(target_cls.id == target_id, target_cls.comment_count > 0)
                .values(comment_count=target_cls.comment_count - 1)
            )
        # 维护父评论的回复计数
        await db.execute(
            update(Comment)
            .where(Comment.id == comment.parent_id, Comment.reply_count > 0)
            .values(reply_count=Comment.reply_count - 1)
        )

    music_id = comment.music_id
    if music_id is not None:
        from echomemory_backend.services.hotness_service import recalculate_music_hot

        await recalculate_music_hot(db, music_id)

    await db.commit()

    if music_id is not None:
        await invalidate_music_detail(music_id)
    elif comment.playlist_id is not None:
        await invalidate_playlist_detail(comment.playlist_id)


async def like_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """点赞评论。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 用户主键。
        comment_id: 评论主键。

    Returns:
        None。

    Raises:
        BusinessError: 评论不存在、目标不可见或不能自赞时抛出 404/403。
    """
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", code=ErrorCode.COMMENT_NOT_FOUND)
    if comment.user_id == user_id:
        raise BusinessError("Cannot like your own comment", code=ErrorCode.PERMISSION_DENIED)

    await _validate_comment_target_visible(db, comment, user_id)

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

    await create_notification(
        db,
        recipient_id=comment.user_id,
        actor_id=user_id,
        type=NotificationType.COMMENT_LIKE,
        target_type="comment",
        target_id=comment_id,
        extra={"content": comment.content[:100]},
    )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()


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
        BusinessError: 评论不存在或不能自踩时抛出 404/403。
    """
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", code=ErrorCode.COMMENT_NOT_FOUND)
    if comment.user_id == user_id:
        raise BusinessError("Cannot dislike your own comment", code=ErrorCode.PERMISSION_DENIED)

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


async def _get_parent_users(
    db: AsyncSession,
    parent_ids: list[int],
) -> dict[int, CommentUserOut]:
    """批量查询父评论的作者信息。

    Args:
        db: SQLAlchemy 异步 Session。
        parent_ids: 父评论主键列表。

    Returns:
        父评论 ID 到作者信息（CommentUserOut）的映射。
    """
    if not parent_ids:
        return {}
    from echomemory_backend.models.user import User

    stmt = (
        select(Comment.id, User)
        .join(User, Comment.user_id == User.id)
        .where(Comment.id.in_(parent_ids))
    )
    result = await db.execute(stmt)
    return {
        comment_id: CommentUserOut.model_validate(user)
        for comment_id, user in result.all()
    }


def build_comment_out(
    comment: Comment,
    liked_ids: set[int],
    disliked_ids: set[int],
    parent_user: CommentUserOut | None = None,
) -> CommentOut:
    """将评论 ORM 实例转换为带互动状态的 CommentOut。

    Args:
        comment: 评论 ORM 实例。
        liked_ids: 当前用户已点赞的评论 ID 集合。
        disliked_ids: 当前用户已点踩的评论 ID 集合。
        parent_user: 父评论作者信息，无父评论时为 None。

    Returns:
        包含 liked_by_me / disliked_by_me / parent_user 的 CommentOut。
    """
    return CommentOut.model_validate(comment).model_copy(
        update={
            "liked_by_me": comment.id in liked_ids,
            "disliked_by_me": comment.id in disliked_ids,
            "parent_user": parent_user,
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
    parent_ids = list({c.parent_id for c in comments if c.parent_id is not None})
    parent_users = await _get_parent_users(db, parent_ids)
    return [
        build_comment_out(
            comment, liked_ids, disliked_ids, parent_users.get(comment.parent_id)
        )
        for comment in comments
    ]
