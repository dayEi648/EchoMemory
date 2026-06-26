"""管理员评论与空间动态审核管理 API。"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query

from echomemory_backend.api.deps import AdminUser, PositiveIntPath, SessionDep
from echomemory_backend.schemas.content_moderation import (
    AdminModeratedContentOut,
    ManualModerationInput,
    PaginatedModeratedContentOut,
    UserContentModerationStatsOut,
)
from echomemory_backend.services import admin_content_moderation_service

router = APIRouter(
    prefix="/admin/content-moderation",
    tags=["admin-content-moderation"],
)
ContentResource = Literal["comments", "space-posts", "playlists", "user-profiles"]


@router.get(
    "/users/{user_id}/stats",
    response_model=UserContentModerationStatsOut,
)
async def admin_get_user_moderation_stats(
    db: SessionDep,
    _: AdminUser,
    user_id: PositiveIntPath,
) -> UserContentModerationStatsOut:
    """获取用户风险、危险和推荐内容统计。"""
    return await admin_content_moderation_service.get_user_stats(db, user_id)


_RESOURCE_TO_TYPE: dict[str, str] = {
    "comments": "comment",
    "space-posts": "space_post",
    "playlists": "playlist",
    "user-profiles": "user_profile",
}


def _content_type(resource: ContentResource) -> str:
    return _RESOURCE_TO_TYPE[resource]


@router.get(
    "/{resource}",
    response_model=PaginatedModeratedContentOut,
)
async def admin_list_content(
    db: SessionDep,
    _: AdminUser,
    resource: ContentResource,
    q: str | None = Query(None, max_length=200),
    user_id: int | None = Query(None, ge=1),
    target_type: str | None = Query(None, max_length=20),
    target_id: int | None = Query(None, ge=1),
    safety_level: str | None = Query(None, max_length=16),
    recommendation_level: str | None = Query(None, max_length=16),
    moderation_status: str | None = Query(None, max_length=16),
    is_deleted: bool | None = None,
    is_recommended: bool | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedModeratedContentOut:
    """筛选查询评论或空间动态。"""
    items, total = await admin_content_moderation_service.list_moderated_content(
        db,
        content_type=_content_type(resource),
        q=q,
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        safety_level=safety_level,
        recommendation_level=recommendation_level,
        moderation_status=moderation_status,
        is_deleted=is_deleted,
        is_recommended=is_recommended,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return PaginatedModeratedContentOut(items=items, total=total)


@router.post(
    "/{resource}/{content_id}/rereview",
    response_model=AdminModeratedContentOut,
)
async def admin_rereview_content(
    db: SessionDep,
    _: AdminUser,
    resource: ContentResource,
    content_id: PositiveIntPath,
) -> AdminModeratedContentOut:
    """请求重新执行 Agent 审核。"""
    return await admin_content_moderation_service.request_rereview(
        db,
        content_type=_content_type(resource),
        content_id=content_id,
    )


@router.post(
    "/{resource}/{content_id}/manual-review",
    response_model=AdminModeratedContentOut,
)
async def admin_manual_review_content(
    db: SessionDep,
    current_admin: AdminUser,
    resource: ContentResource,
    content_id: PositiveIntPath,
    data: ManualModerationInput,
) -> AdminModeratedContentOut:
    """人工设置审核分值与结果。"""
    return await admin_content_moderation_service.apply_manual_review(
        db,
        content_type=_content_type(resource),
        content_id=content_id,
        reviewer_user_id=current_admin.id,
        decision=data,
    )


@router.post(
    "/{resource}/{content_id}/restore",
    response_model=AdminModeratedContentOut,
)
async def admin_restore_content(
    db: SessionDep,
    _: AdminUser,
    resource: ContentResource,
    content_id: PositiveIntPath,
) -> AdminModeratedContentOut:
    """恢复因自动审核逻辑删除的内容。"""
    return await admin_content_moderation_service.restore_content(
        db,
        content_type=_content_type(resource),
        content_id=content_id,
    )
