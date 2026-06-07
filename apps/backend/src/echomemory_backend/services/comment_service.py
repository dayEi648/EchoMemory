from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from echomemory_backend.models.comment import Comment, CommentDislike, CommentLike
from echomemory_backend.models.music import Music
from echomemory_backend.models.playlist import Playlist
from echomemory_backend.models.space_post import SpacePost
from echomemory_backend.services.user_service import BusinessError


_VALID_TARGET_TYPES = ("music", "playlist", "space_post")


async def _validate_target_exists(
    db: AsyncSession, target_type: str, target_id: int
) -> None:
    """校验评论目标是否存在且可见。"""
    if target_type == "music":
        target = await db.get(Music, target_id)
        if target is None or not target.is_published:
            raise BusinessError("Target not found", 404)
    elif target_type == "playlist":
        target = await db.get(Playlist, target_id)
        if target is None:
            raise BusinessError("Target not found", 404)
    elif target_type == "space_post":
        target = await db.get(SpacePost, target_id)
        if target is None or target.is_deleted:
            raise BusinessError("Target not found", 404)


async def _resolve_parent(
    db: AsyncSession,
    parent_id: int | None,
    target_type: str,
    target_id: int,
) -> tuple[int | None, bool]:
    """根据 parent_id 解析 root_id 和 is_nested_reply。

    返回 (root_id, is_nested_reply)。
    同时校验 parent 是否属于同一个 target。
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
    """加载 user 关联后的单条评论。"""
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
    """发表评论（含回复）。"""
    if target_type not in _VALID_TARGET_TYPES:
        raise BusinessError("Invalid target_type", 400)

    await _validate_target_exists(db, target_type, target_id)
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
    comment_id = comment.id
    await db.commit()
    return await _get_comment_with_user(db, comment_id)


async def list_comments(
    db: AsyncSession,
    target_type: str,
    target_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[Comment]:
    """查询指定目标的 root 评论列表，排除已删除，按时间倒序。"""
    if target_type not in _VALID_TARGET_TYPES:
        raise BusinessError("Invalid target_type", 400)

    target_filter = {
        "music": Comment.music_id == target_id,
        "playlist": Comment.playlist_id == target_id,
        "space_post": Comment.space_post_id == target_id,
    }[target_type]

    stmt = (
        select(Comment)
        .where(target_filter)
        .where(Comment.parent_id.is_(None))
        .where(Comment.is_deleted.is_(False))
        .order_by(desc(Comment.created_at))
        .limit(limit)
        .offset(offset)
        .options(selectinload(Comment.user))
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """软删除评论。仅允许评论作者操作。"""
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)
    if comment.user_id != user_id:
        raise BusinessError("Permission denied", 403)

    comment.is_deleted = True
    await db.commit()


async def like_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """点赞评论。已点赞则静默成功。"""
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)

    existing = await db.get(CommentLike, (comment_id, user_id))
    if existing is not None:
        return

    db.add(CommentLike(comment_id=comment_id, user_id=user_id))
    await db.commit()


async def unlike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """取消点赞。未点赞则静默成功。"""
    existing = await db.get(CommentLike, (comment_id, user_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()


async def dislike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """点踩评论。已点踩则静默成功。"""
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.is_deleted:
        raise BusinessError("Comment not found", 404)

    existing = await db.get(CommentDislike, (comment_id, user_id))
    if existing is not None:
        return

    db.add(CommentDislike(comment_id=comment_id, user_id=user_id))
    await db.commit()


async def undislike_comment(db: AsyncSession, user_id: int, comment_id: int) -> None:
    """取消点踩。未点踩则静默成功。"""
    existing = await db.get(CommentDislike, (comment_id, user_id))
    if existing is not None:
        await db.delete(existing)
        await db.commit()
