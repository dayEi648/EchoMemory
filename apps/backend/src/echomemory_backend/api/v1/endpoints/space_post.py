"""空间动态（Space Post）API 路由端点，支持用户发布、查看、点赞、删除动态及管理员硬删除。"""

import os

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from echomemory_backend.api.deps import ActiveUser, AdminUser, SessionDep
from echomemory_backend.api.v1.endpoints._upload_helpers import upload_optional_image
from echomemory_backend.core.oss_client import delete_object_by_url
from echomemory_backend.schemas.space_post import SpacePostListOut, SpacePostOut
from echomemory_backend.services import space_post_service

router = APIRouter(prefix="/space-posts", tags=["space-posts"])


_ALLOWED_FILE_EXTS = {"mp3", "flac", "wav", "ogg", "aac", "lrc", "jpg", "jpeg", "png"}


def _safe_ext(filename: str | None, default: str) -> str:
    """从上传文件名中安全地提取扩展名，不在白名单时回退到默认值。"""
    if not filename:
        return default
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    return ext if ext in _ALLOWED_FILE_EXTS else default


# ---------------------------------------------------------------------------
# 用户接口
# ---------------------------------------------------------------------------

@router.post("/", response_model=SpacePostOut, status_code=status.HTTP_201_CREATED)
async def create_space_post(
    db: SessionDep,
    current_user: ActiveUser,
    content: str | None = Form(None, max_length=2000),
    is_private: bool = Form(False),
    files: list[UploadFile] = File([]),
):
    """创建空间动态。支持文字 + 可选多图上传。"""
    if not content and not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Content or at least one file is required",
        )
    uploaded_urls: list[str] = []
    try:
        for file in files:
            url = await upload_optional_image(
                file,
                folder="space_post_images",
                prefix=str(current_user.id),
                detail_name="File",
            )
            if url:
                uploaded_urls.append(url)

        post = await space_post_service.create_space_post(
            db,
            user_id=current_user.id,
            content=content,
            is_private=is_private,
            image_urls=uploaded_urls,
        )
    except HTTPException:
        for url in uploaded_urls:
            await delete_object_by_url(url)
        raise
    except (RuntimeError, ValueError, IntegrityError, SQLAlchemyError):
        for url in uploaded_urls:
            await delete_object_by_url(url)
        raise

    post = await space_post_service.get_space_post_by_id(db, post.id)
    return post


@router.get("/{post_id}", response_model=SpacePostOut)
async def get_space_post(
    db: SessionDep,
    current_user: ActiveUser,
    post_id: int,
):
    """获取动态详情。已删除或无权查看 private 时返回 404/403。"""
    post = await space_post_service.get_space_post_by_id(db, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post.is_private and post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this post",
        )
    return post


@router.get("/", response_model=list[SpacePostListOut])
async def list_space_posts(
    db: SessionDep,
    current_user: ActiveUser,
    user_id: int | None = Query(None, description="查看指定用户的动态，不传则查看自己"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出用户动态。"""
    target_user_id = user_id if user_id is not None else current_user.id
    return await space_post_service.list_space_posts(
        db,
        target_user_id=target_user_id,
        viewer_user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space_post(
    db: SessionDep,
    current_user: ActiveUser,
    post_id: int,
):
    """软删除自己的动态。"""
    post = await space_post_service.get_space_post_by_id(db, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this post",
        )
    await space_post_service.soft_delete_space_post(db, post)
    return None


@router.post("/{post_id}/like", status_code=status.HTTP_201_CREATED)
async def like_space_post(
    db: SessionDep,
    current_user: ActiveUser,
    post_id: int,
):
    """点赞动态。"""
    post = await space_post_service.get_space_post_by_id(db, post_id)
    if post is None or post.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    await space_post_service.like_space_post(db, current_user.id, post_id)
    return None


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_space_post(
    db: SessionDep,
    current_user: ActiveUser,
    post_id: int,
):
    """取消点赞。"""
    await space_post_service.unlike_space_post(db, current_user.id, post_id)
    return None


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.delete("/admin/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_hard_delete_space_post(
    db: SessionDep,
    _: AdminUser,
    post_id: int,
):
    """管理员硬删除动态，并清理已上传的 OSS 图片。"""
    image_urls = await space_post_service.hard_delete_space_post(db, post_id)

    for url in image_urls:
        await delete_object_by_url(url)
    return None
