"""用户收藏相关 API 路由端点，提供音乐喜欢、专辑收藏、歌单收藏功能。"""
from echomemory_backend.core.exceptions.codes import HttpStatus

from fastapi import APIRouter, Query

from echomemory_backend.api.deps import ActiveUser, PositiveIntPath, SessionDep
from echomemory_backend.schemas.collection import (
    AlbumCollectionOut,
    PaginatedAlbumCollectionOut,
    PaginatedMusicCollectionOut,
    PaginatedPlaylistCollectionOut,
    PlaylistCollectionOut,
)
from echomemory_backend.services import collection_service

router = APIRouter(prefix="/collections", tags=["collections"])


# ---------------------------------------------------------------------------
# 音乐喜欢（对应“我喜欢的音乐”歌单）
# ---------------------------------------------------------------------------


@router.delete("/musics/{music_id}", status_code=HttpStatus.NO_CONTENT)
async def uncollect_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: PositiveIntPath,
):
    """取消收藏音乐。未收藏则静默成功。"""
    await collection_service.uncollect_music(db, current_user.id, music_id)
    return None


@router.get("/musics", response_model=PaginatedMusicCollectionOut)
async def list_music_collections(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的收藏音乐列表（按收藏时间倒序）。"""
    return await collection_service.list_music_collections(
        db, current_user.id, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# 专辑收藏
# ---------------------------------------------------------------------------


@router.post("/albums/{album_id}", response_model=AlbumCollectionOut, status_code=HttpStatus.CREATED)
async def collect_album(
    db: SessionDep,
    current_user: ActiveUser,
    album_id: PositiveIntPath,
):
    """收藏专辑。已收藏则静默返回。"""
    return await collection_service.collect_album(db, current_user.id, album_id)


@router.delete("/albums/{album_id}", status_code=HttpStatus.NO_CONTENT)
async def uncollect_album(
    db: SessionDep,
    current_user: ActiveUser,
    album_id: PositiveIntPath,
):
    """取消收藏专辑。未收藏则静默成功。"""
    await collection_service.uncollect_album(db, current_user.id, album_id)
    return None


@router.get("/albums", response_model=PaginatedAlbumCollectionOut)
async def list_album_collections(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的收藏专辑列表（按收藏时间倒序）。"""
    return await collection_service.list_album_collections(
        db, current_user.id, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# 歌单收藏
# ---------------------------------------------------------------------------


@router.post(
    "/playlists/{playlist_id}", response_model=PlaylistCollectionOut, status_code=HttpStatus.CREATED
)
async def collect_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: PositiveIntPath,
):
    """收藏歌单。已收藏则静默返回。"""
    return await collection_service.collect_playlist(db, current_user.id, playlist_id)


@router.delete("/playlists/{playlist_id}", status_code=HttpStatus.NO_CONTENT)
async def uncollect_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: PositiveIntPath,
):
    """取消收藏歌单。未收藏则静默成功。"""
    await collection_service.uncollect_playlist(db, current_user.id, playlist_id)
    return None


@router.get("/playlists", response_model=PaginatedPlaylistCollectionOut)
async def list_playlist_collections(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的收藏歌单列表（按收藏时间倒序）。"""
    return await collection_service.list_playlist_collections(
        db, current_user.id, limit=limit, offset=offset
    )
