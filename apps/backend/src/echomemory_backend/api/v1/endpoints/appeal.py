"""内容申诉 API — 用户发起申诉 + 管理员处理。"""

from fastapi import APIRouter, Query

from echomemory_backend.api.deps import ActiveUser, AdminUser, PositiveIntPath, SessionDep
from echomemory_backend.schemas.content_appeal import (
    AdminAppealResolve,
    AppealCreate,
    AppealOut,
)
from echomemory_backend.services import appeal_service

router = APIRouter(prefix="/moderation/appeals", tags=["appeals"])

# ---- 用户端点 ----

@router.post("/", response_model=AppealOut)
async def create_appeal(
    db: SessionDep,
    current_user: ActiveUser,
    appeal_in: AppealCreate,
) -> AppealOut:
    """对审核决定发起申诉。"""
    return await appeal_service.create_appeal(
        db,
        user_id=current_user.id,
        appeal_in=appeal_in,
    )


# ---- 管理员端点 ----

@router.get("/admin", response_model=dict)
async def admin_list_appeals(
    db: SessionDep,
    _: AdminUser,
    status: str | None = Query(None, max_length=16),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """管理员分页查询申诉列表。"""
    items, total = await appeal_service.list_appeals(
        db, status=status, limit=limit, offset=offset
    )
    return {"items": items, "total": total}


@router.post("/admin/{appeal_id}/approve", response_model=AppealOut)
async def admin_approve_appeal(
    db: SessionDep,
    admin: AdminUser,
    appeal_id: PositiveIntPath,
    body: AdminAppealResolve,
) -> AppealOut:
    """批准申诉 — 恢复内容。"""
    return await appeal_service.approve_appeal(
        db,
        appeal_id=appeal_id,
        reviewer_user_id=admin.id,
        admin_note=body.admin_note,
    )


@router.post("/admin/{appeal_id}/deny", response_model=AppealOut)
async def admin_deny_appeal(
    db: SessionDep,
    admin: AdminUser,
    appeal_id: PositiveIntPath,
    body: AdminAppealResolve,
) -> AppealOut:
    """驳回申诉 — 维持审核决定。"""
    return await appeal_service.deny_appeal(
        db,
        appeal_id=appeal_id,
        reviewer_user_id=admin.id,
        admin_note=body.admin_note,
    )
