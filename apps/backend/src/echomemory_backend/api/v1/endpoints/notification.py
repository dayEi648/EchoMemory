"""通知（Notification）API 路由端点。"""

from fastapi import APIRouter, Query, status

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.schemas.notification import (
    NotificationOut,
    PaginatedNotificationOut,
    UnreadSummaryOut,
)
from echomemory_backend.services import message_service, notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/unread-summary", response_model=UnreadSummaryOut)
async def get_unread_summary(
    db: SessionDep,
    current_user: ActiveUser,
):
    """汇总当前用户未读通知数与未读私信数，供铃铛入口快速展示小红点。"""
    notification_unread = await notification_service.count_unread_notifications(
        db, current_user.id
    )
    message_unread = await message_service.total_unread_messages(db, current_user.id)
    return UnreadSummaryOut(
        notification_unread=notification_unread,
        message_unread=message_unread,
    )


@router.get("/", response_model=PaginatedNotificationOut)
async def list_notifications(
    db: SessionDep,
    current_user: ActiveUser,
    only_unread: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出当前用户的通知，支持只看未读。"""
    result = await notification_service.list_notifications(
        db,
        recipient_id=current_user.id,
        limit=limit,
        offset=offset,
        only_unread=only_unread,
    )
    items = [NotificationOut.model_validate(n) for n in result["items"]]
    return PaginatedNotificationOut(items=items, total=result["total"])


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    db: SessionDep,
    current_user: ActiveUser,
    notification_id: int,
):
    """将单条通知标记为已读。"""
    await notification_service.mark_notification_read(
        db,
        recipient_id=current_user.id,
        notification_id=notification_id,
    )
    return None


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_notifications_read(
    db: SessionDep,
    current_user: ActiveUser,
):
    """将当前用户的全部通知标记为已读。"""
    await notification_service.mark_all_notifications_read(db, current_user.id)
    return None
