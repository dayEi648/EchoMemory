"""系统日志管理 API 端点，仅供管理员查看后端日志。"""

from fastapi import APIRouter, Query

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.schemas.system_log import (
    PaginatedSystemLogOut,
    SystemLogDetailOut,
    SystemLogListParams,
    SystemLogOut,
)
from echomemory_backend.services import log_service

router = APIRouter(prefix="/admin/logs", tags=["admin-logs"])


@router.get("", response_model=PaginatedSystemLogOut)
async def admin_list_logs(
    db: SessionDep,
    _: AdminUser,
    level: str | None = Query(None, description="日志等级: WARNING/ERROR/CRITICAL"),
    start_time: str | None = Query(None, description="起始时间 ISO 8601"),
    end_time: str | None = Query(None, description="结束时间 ISO 8601"),
    q: str | None = Query(None, description="消息关键词模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedSystemLogOut:
    """以管理员身份分页查询系统日志。"""
    params = SystemLogListParams(
        level=level,
        start_time=start_time,
        end_time=end_time,
        q=q,
        limit=limit,
        offset=offset,
    )
    items, total = await log_service.list_logs(db, params)
    return PaginatedSystemLogOut(
        items=[SystemLogOut.from_orm(item) for item in items], total=total
    )


@router.get("/{log_id}", response_model=SystemLogDetailOut)
async def admin_get_log(
    db: SessionDep,
    _: AdminUser,
    log_id: int,
) -> SystemLogDetailOut:
    """以管理员身份获取单条系统日志详情。"""
    log = await log_service.get_log(db, log_id)
    return SystemLogDetailOut.model_validate(log)
