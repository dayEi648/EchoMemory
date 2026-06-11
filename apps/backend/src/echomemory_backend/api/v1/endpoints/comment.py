"""评论相关 API 端点，提供评论的增删查及互动（点赞/点踩）功能。"""

from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import ActiveUser, OptionalUser, SessionDep
from echomemory_backend.schemas.comment import CommentCreate, CommentOut, PaginatedCommentOut
from echomemory_backend.services import comment_service

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/replies/{root_id}", response_model=list[CommentOut])
async def list_replies(
    db: SessionDep,
    root_id: int,
):
    """获取指定根评论的所有非删除回复（按时间正序）。公开接口，无需登录。"""
    return await comment_service.list_replies(db, root_id=root_id)


@router.post("/", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    db: SessionDep,
    current_user: ActiveUser,
    data: CommentCreate,
):
    """发表评论。支持回复（parent_id）。"""
    return await comment_service.create_comment(
        db,
        user_id=current_user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        content=data.content,
        parent_id=data.parent_id,
    )


@router.get("/{target_type}/{target_id}", response_model=PaginatedCommentOut)
async def list_comments(
    db: SessionDep,
    target_type: str,
    target_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: OptionalUser = None,
):
    """获取指定目标的 root 评论列表（排除已删除，按时间倒序）。公开接口，无需登录。"""
    viewer_id = current_user.id if current_user is not None else None
    return await comment_service.list_comments(
        db,
        target_type=target_type,
        target_id=target_id,
        viewer_user_id=viewer_id,
        limit=limit,
        offset=offset,
    )


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """软删除自己的评论。"""
    await comment_service.delete_comment(db, current_user.id, comment_id)
    return None


@router.post("/{comment_id}/like", status_code=status.HTTP_201_CREATED)
async def like_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """点赞评论。已点赞则静默成功。"""
    await comment_service.like_comment(db, current_user.id, comment_id)
    return None


@router.delete("/{comment_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """取消点赞。未点赞则静默成功。"""
    await comment_service.unlike_comment(db, current_user.id, comment_id)
    return None


@router.post("/{comment_id}/dislike", status_code=status.HTTP_201_CREATED)
async def dislike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """点踩评论。已点踩则静默成功。"""
    await comment_service.dislike_comment(db, current_user.id, comment_id)
    return None


@router.delete("/{comment_id}/dislike", status_code=status.HTTP_204_NO_CONTENT)
async def undislike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """取消点踩。未点踩则静默成功。"""
    await comment_service.undislike_comment(db, current_user.id, comment_id)
    return None
