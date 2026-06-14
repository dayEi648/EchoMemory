"""播放历史相关接口。提供播放记录创建、查询、单条删除及清空等操作。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.schemas.play_history import (
    PaginatedPlayHistoryOut,
    PlayHistoryCreate,
    PlayHistoryOut,
)
from echomemory_backend.services import play_history_service

router = APIRouter(prefix="/play-history", tags=["play-history"])


@router.post("/", response_model=PlayHistoryOut, status_code=HttpStatus.CREATED)
async def record_play(
    db: SessionDep,
    current_user: ActiveUser,
    data: PlayHistoryCreate,
):
    """记录一次播放。"""
    user_id = current_user.id
    await play_history_service.create_play_history(
        db, user_id, data.music_id, playlist_id=data.playlist_id
    )

    # 重新加载关联数据以匹配 PlayHistoryOut
    histories = await play_history_service.list_play_history(
        db, user_id, limit=1, offset=0
    )
    return histories["items"][0]


@router.get("/", response_model=PaginatedPlayHistoryOut)
async def list_play_history(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的播放历史（按时间倒序）。"""
    return await play_history_service.list_play_history(
        db, current_user.id, limit=limit, offset=offset
    )


@router.delete("/{history_id}", status_code=HttpStatus.NO_CONTENT)
async def delete_play_history(
    db: SessionDep,
    current_user: ActiveUser,
    history_id: int,
):
    """删除单条播放记录。"""
    await play_history_service.delete_play_history(
        db, current_user.id, history_id
    )


@router.delete("/", status_code=HttpStatus.NO_CONTENT)
async def clear_play_history(
    db: SessionDep,
    current_user: ActiveUser,
):
    """清空全部播放历史。"""
    await play_history_service.clear_play_history(db, current_user.id)
