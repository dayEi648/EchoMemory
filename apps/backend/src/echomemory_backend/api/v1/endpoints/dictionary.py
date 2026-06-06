from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.schemas.dictionary import (
    DictionaryItemCreate,
    DictionaryItemOut,
    DictionaryItemUpdate,
)
from echomemory_backend.services import dictionary_service
from echomemory_backend.services.user_service import BusinessError

router = APIRouter(prefix="/dictionary", tags=["dictionary"])


@router.post("/{dictionary_type}", response_model=DictionaryItemOut, status_code=status.HTTP_201_CREATED)
async def create_dictionary_item(
    db: SessionDep,
    _: AdminUser,
    dictionary_type: str,
    item_in: DictionaryItemCreate,
):
    """管理员：创建字典项。"""
    try:
        return await dictionary_service.create_dictionary_item(
            db, dictionary_type, item_in.name
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{dictionary_type}", response_model=list[DictionaryItemOut])
async def list_dictionary_items(
    db: SessionDep,
    dictionary_type: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """公开：分页列出字典项。"""
    try:
        return await dictionary_service.list_dictionary_items(
            db, dictionary_type, limit=limit, offset=offset
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{dictionary_type}/{item_id}", response_model=DictionaryItemOut)
async def get_dictionary_item(
    db: SessionDep,
    dictionary_type: str,
    item_id: int,
):
    """公开：获取单个字典项。"""
    try:
        item = await dictionary_service.get_dictionary_item_by_id(
            db, dictionary_type, item_id
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dictionary item not found")
    return item


@router.patch("/{dictionary_type}/{item_id}", response_model=DictionaryItemOut)
async def update_dictionary_item(
    db: SessionDep,
    _: AdminUser,
    dictionary_type: str,
    item_id: int,
    item_in: DictionaryItemUpdate,
):
    """管理员：更新字典项名称。"""
    if item_in.name is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Name is required for update",
        )
    try:
        return await dictionary_service.update_dictionary_item(
            db, dictionary_type, item_id, item_in.name
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.delete("/{dictionary_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dictionary_item(
    db: SessionDep,
    _: AdminUser,
    dictionary_type: str,
    item_id: int,
):
    """管理员：删除字典项（仅当未被引用时）。"""
    try:
        await dictionary_service.delete_dictionary_item(db, dictionary_type, item_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return None
