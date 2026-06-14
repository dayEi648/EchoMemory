"""评论相关 API 端点，提供评论的增删查及互动（点赞/点踩）功能。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import ActiveUser, OptionalUser, SessionDep
from echomemory_backend.schemas.comment import CommentCreate, CommentOut, PaginatedCommentOut
from echomemory_backend.services import comment_service

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("/replies/{root_id}", response_model=list[CommentOut])
async def list_replies(
    db: SessionDep,
    root_id: int,
    current_user: OptionalUser = None,
):
    """获取指定根评论的所有非删除回复（按时间正序）。公开接口，无需登录。"""
    replies = await comment_service.list_replies(db, root_id=root_id)
    viewer_id = current_user.id if current_user is not None else None
    return await comment_service.build_comment_outs(db, replies, viewer_id)


@router.post("/", response_model=CommentOut, status_code=HttpStatus.CREATED)
async def create_comment(
    db: SessionDep,
    current_user: ActiveUser,
    data: CommentCreate,
):
    """发表评论。支持回复（parent_id）。"""
    comment = await comment_service.create_comment(
        db,
        user_id=current_user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        content=data.content,
        parent_id=data.parent_id,
    )
    return comment_service.build_comment_out(comment, set(), set())


@router.get("/{target_type}/{target_id}", response_model=PaginatedCommentOut)
async def list_comments(
    db: SessionDep,
    target_type: str,
    target_id: int,
    sort_by: str = Query("recommended", description="排序: recommended / latest / likes"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: OptionalUser = None,
):
    """获取指定目标的 root 评论列表。公开接口，无需登录。"""
    viewer_id = current_user.id if current_user is not None else None
    result = await comment_service.list_comments(
        db,
        target_type=target_type,
        target_id=target_id,
        viewer_user_id=viewer_id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )
    items = await comment_service.build_comment_outs(db, result["items"], viewer_id)
    return PaginatedCommentOut(items=items, total=result["total"])


@router.delete("/{comment_id}", status_code=HttpStatus.NO_CONTENT)
async def delete_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """软删除自己的评论。"""
    await comment_service.delete_comment(db, current_user.id, comment_id)
    return None


@router.post("/{comment_id}/like", status_code=HttpStatus.CREATED)
async def like_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """点赞评论。已点赞则静默成功。"""
    await comment_service.like_comment(db, current_user.id, comment_id)
    return None


@router.delete("/{comment_id}/like", status_code=HttpStatus.NO_CONTENT)
async def unlike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """取消点赞。未点赞则静默成功。"""
    await comment_service.unlike_comment(db, current_user.id, comment_id)
    return None


@router.post("/{comment_id}/dislike", status_code=HttpStatus.CREATED)
async def dislike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """点踩评论。已点踩则静默成功。"""
    await comment_service.dislike_comment(db, current_user.id, comment_id)
    return None


@router.delete("/{comment_id}/dislike", status_code=HttpStatus.NO_CONTENT)
async def undislike_comment(
    db: SessionDep,
    current_user: ActiveUser,
    comment_id: int,
):
    """取消点踩。未点踩则静默成功。"""
    await comment_service.undislike_comment(db, current_user.id, comment_id)
    return None
