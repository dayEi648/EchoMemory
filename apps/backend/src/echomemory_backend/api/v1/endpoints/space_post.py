"""空间动态（Space Post）API 路由端点，支持用户发布、查看、点赞、删除动态及管理员硬删除。"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import ActiveUser, AdminUser, SessionDep
from echomemory_backend.api.v1.endpoints._upload_helpers import (
    UploadCollector,
    upload_optional_image,
)
from echomemory_backend.core.oss_client import delete_object_by_url
from echomemory_backend.schemas.space_post import PaginatedSpacePostListOut, SpacePostListOut, SpacePostOut
from echomemory_backend.services import space_post_service
from echomemory_backend.services.space_post_service import can_view_space_post

router = APIRouter(prefix="/space-posts", tags=["space-posts"])


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
    async with UploadCollector() as uploads:
        for file in files:
            uploads.add(
                await upload_optional_image(
                    file,
                    folder="space_post_images",
                    prefix=str(current_user.id),
                    detail_name="File",
                )
            )

        post = await space_post_service.create_space_post(
            db,
            user_id=current_user.id,
            content=content,
            is_private=is_private,
            image_urls=uploads.urls,
        )

    post = await space_post_service.get_space_post_by_id(db, post.id)
    return (
        await space_post_service.build_space_post_outs(db, [post], current_user.id)
    )[0]


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
    if not can_view_space_post(current_user.id, post):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this post",
        )
    return (
        await space_post_service.build_space_post_outs(db, [post], current_user.id)
    )[0]


@router.get("/", response_model=PaginatedSpacePostListOut)
async def list_space_posts(
    db: SessionDep,
    current_user: ActiveUser,
    user_id: int | None = Query(None, description="查看指定用户的动态，不传则查看自己"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出用户动态。"""
    target_user_id = user_id if user_id is not None else current_user.id
    result = await space_post_service.list_space_posts(
        db,
        target_user_id=target_user_id,
        viewer_user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    items = await space_post_service.build_space_post_outs(
        db,
        result["items"],
        current_user.id,
        as_list_item=True,
    )
    return PaginatedSpacePostListOut(items=items, total=result["total"])


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
    if post is None or not can_view_space_post(current_user.id, post):
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


@router.post("/forward", response_model=SpacePostOut, status_code=status.HTTP_201_CREATED)
async def forward_to_space(
    db: SessionDep,
    current_user: ActiveUser,
    source_type: str = Form(..., description="space_post / music / album / playlist"),
    source_id: int = Form(..., gt=0),
    content: str | None = Form(None, max_length=2000),
):
    """转发内容到自己的空间动态。"""
    post = await space_post_service.forward_to_space(
        db,
        current_user.id,
        source_type=source_type,
        source_id=source_id,
        content=content,
    )
    # 重新加载以填充 images 关联（转发无图片，但需避免懒加载 MissingGreenlet）
    post = await space_post_service.get_space_post_by_id(db, post.id)
    return (await space_post_service.build_space_post_outs(db, [post], current_user.id))[0]


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
