"""用户收藏与发布标记相关的 API 路由端点，提供音乐、专辑、歌单的收藏/取消收藏以及已发布音乐标记功能。"""

from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.schemas.collection import (
    AlbumCollectionOut,
    MusicCollectionOut,
    PlaylistCollectionOut,
    ReleaseOut,
)
from echomemory_backend.services import collection_service

router = APIRouter(prefix="/collections", tags=["collections"])


# ---------------------------------------------------------------------------
# 音乐收藏
# ---------------------------------------------------------------------------


@router.post("/musics/{music_id}", response_model=MusicCollectionOut, status_code=status.HTTP_201_CREATED)
async def collect_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: int,
):
    """收藏音乐。已收藏则静默返回。"""
    return await collection_service.collect_music(db, current_user.id, music_id)


@router.delete("/musics/{music_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uncollect_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: int,
):
    """取消收藏音乐。未收藏则静默成功。"""
    await collection_service.uncollect_music(db, current_user.id, music_id)
    return None


@router.get("/musics", response_model=list[MusicCollectionOut])
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


@router.post("/albums/{album_id}", response_model=AlbumCollectionOut, status_code=status.HTTP_201_CREATED)
async def collect_album(
    db: SessionDep,
    current_user: ActiveUser,
    album_id: int,
):
    """收藏专辑。已收藏则静默返回。"""
    return await collection_service.collect_album(db, current_user.id, album_id)


@router.delete("/albums/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uncollect_album(
    db: SessionDep,
    current_user: ActiveUser,
    album_id: int,
):
    """取消收藏专辑。未收藏则静默成功。"""
    await collection_service.uncollect_album(db, current_user.id, album_id)
    return None


@router.get("/albums", response_model=list[AlbumCollectionOut])
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
    "/playlists/{playlist_id}", response_model=PlaylistCollectionOut, status_code=status.HTTP_201_CREATED
)
async def collect_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
):
    """收藏歌单。已收藏则静默返回。"""
    return await collection_service.collect_playlist(db, current_user.id, playlist_id)


@router.delete("/playlists/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uncollect_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
):
    """取消收藏歌单。未收藏则静默成功。"""
    await collection_service.uncollect_playlist(db, current_user.id, playlist_id)
    return None


@router.get("/playlists", response_model=list[PlaylistCollectionOut])
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


# ---------------------------------------------------------------------------
# 已发布音乐标记
# ---------------------------------------------------------------------------


@router.post("/releases/{music_id}", response_model=ReleaseOut, status_code=status.HTTP_201_CREATED)
async def release_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: int,
):
    """标记音乐为已发布。已标记则静默返回。"""
    return await collection_service.release_music(db, current_user.id, music_id)


@router.delete("/releases/{music_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unrelease_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: int,
):
    """取消已发布音乐标记。未标记则静默成功。"""
    await collection_service.unrelease_music(db, current_user.id, music_id)
    return None


@router.get("/releases", response_model=list[ReleaseOut])
async def list_releases(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的已发布音乐列表（按标记时间倒序）。"""
    return await collection_service.list_releases(
        db, current_user.id, limit=limit, offset=offset
    )
