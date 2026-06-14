"""轮播推图 API 端点。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

from fastapi import APIRouter, HTTPException, status

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.schemas.carousel import (
    CarouselItemCreate,
    CarouselItemOut,
    CarouselItemUpdate,
    ReorderRequest,
)
from echomemory_backend.services import carousel_service

router = APIRouter(prefix="/carousel", tags=["carousel"])


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CarouselItemOut])
async def list_carousel(db: SessionDep):
    """公开：列出所有轮播推图（含解析后的封面 URL）。"""
    items = await carousel_service.list_carousel_items(db)
    return items


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.post("/admin", response_model=CarouselItemOut, status_code=HttpStatus.CREATED)
async def create_carousel_item(
    db: SessionDep,
    _: AdminUser,
    item_in: CarouselItemCreate,
):
    """管理员：新增轮播推图。"""
    item = await carousel_service.create_carousel_item(
        db,
        item_type=item_in.type,
        target_id=item_in.target_id,
        title=item_in.title,
        description=item_in.description,
    )
    return item


@router.patch("/admin/{item_id}", response_model=CarouselItemOut)
async def update_carousel_item(
    db: SessionDep,
    _: AdminUser,
    item_id: str,
    item_in: CarouselItemUpdate,
):
    """管理员：修改轮播推图的标题/描述。"""
    item = await carousel_service.update_carousel_item(
        db,
        item_id=item_id,
        title=item_in.title,
        description=item_in.description,
    )
    if item is None:
        raise HTTPException(status_code=HttpStatus.NOT_FOUND, detail="推图不存在")
    return item


@router.delete("/admin/{item_id}", status_code=HttpStatus.NO_CONTENT)
async def delete_carousel_item(
    _: AdminUser,
    item_id: str,
):
    """管理员：删除轮播推图。"""
    deleted = await carousel_service.delete_carousel_item(item_id)
    if not deleted:
        raise HTTPException(status_code=HttpStatus.NOT_FOUND, detail="推图不存在")
    return None


@router.patch("/admin/reorder", status_code=HttpStatus.NO_CONTENT)
async def reorder_carousel_items(
    _: AdminUser,
    body: ReorderRequest,
):
    """管理员：调整轮播推图顺序（按 ID 数组顺序排列）。"""
    ok = await carousel_service.reorder_carousel_items(body.ids)
    if not ok:
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="ID 列表与实际推图数量不匹配",
        )
    return None
