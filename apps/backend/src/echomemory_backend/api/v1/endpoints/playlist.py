"""歌单（Playlist）相关 API 端点。

提供歌单的创建、查询、更新、删除以及歌单内歌曲的增删操作。
"""

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.api.v1.endpoints._upload_helpers import upload_optional_image
from echomemory_backend.core import oss_client
from echomemory_backend.schemas.playlist import PaginatedPlaylistListOut, PaginatedPlaylistMembershipOut, PlaylistOut, PlaylistUpdate
from echomemory_backend.services import collection_service, playlist_service

router = APIRouter(prefix="/playlists", tags=["playlists"])


# ---------------------------------------------------------------------------
# 歌单 CRUD
# ---------------------------------------------------------------------------

@router.post("/", response_model=PlaylistOut, status_code=status.HTTP_201_CREATED)
async def create_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    title: str = Form(..., min_length=1, max_length=128),
    description: str | None = Form(None, max_length=500),
    is_private: bool = Form(False),
    cover_icon: UploadFile | None = File(None),
):
    """创建歌单。

    接收 multipart/form-data，可选上传封面图片。
    标签由系统根据歌曲收藏自动计算，不允许手动编辑。
    """
    user_id = current_user.id
    cover_icon_url: str | None = None
    uploaded_urls: list[str] = []

    cover_icon_url = await upload_optional_image(
        cover_icon,
        folder="playlist_covers",
        prefix="icon",
        detail_name="Cover icon",
    )
    if cover_icon_url:
        uploaded_urls.append(cover_icon_url)

    try:
        playlist = await playlist_service.create_playlist(
            db,
            user_id=user_id,
            title=title,
            description=description,
            is_private=is_private,
            cover_icon_url=cover_icon_url,
        )
    except HTTPException:
        raise
    except Exception:
        for url in uploaded_urls:
            await oss_client.delete_object_by_url(url)
        raise

    # 重新加载完整关联数据以匹配 PlaylistOut
    playlist = await playlist_service.get_playlist_by_id(db, playlist.id)
    return playlist


@router.get("/", response_model=PaginatedPlaylistListOut)
async def list_playlists(
    db: SessionDep,
    current_user: ActiveUser,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询我的歌单列表（按创建时间倒序）。"""
    return await playlist_service.list_user_playlists(
        db, current_user.id, limit=limit, offset=offset
    )


# 注意：/search、/public 必须排在 /{playlist_id} 之前。
@router.get("/search", response_model=PaginatedPlaylistListOut)
async def search_playlists(
    db: SessionDep,
    q: str | None = Query(None, description="按标题模糊搜索"),
    emotion_tag_id: int | None = Query(None, description="按情绪标签 ID 筛选"),
    interest_tag_id: int | None = Query(None, description="按兴趣标签 ID 筛选"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """按标题模糊搜索公开歌单，支持标签筛选。"""
    return await playlist_service.search_playlists(
        db,
        q=q,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        limit=limit,
        offset=offset,
    )


@router.get("/public", response_model=PaginatedPlaylistListOut)
async def list_public_playlists(
    db: SessionDep,
    user_id: int = Query(..., ge=1, description="目标用户 ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """查询指定用户的公开歌单列表。"""
    return await playlist_service.list_user_public_playlists(
        db, user_id=user_id, limit=limit, offset=offset
    )


@router.get("/membership/musics/{music_id}", response_model=PaginatedPlaylistMembershipOut)
async def list_playlist_membership_for_music(
    db: SessionDep,
    current_user: ActiveUser,
    music_id: int,
):
    """查询我的歌单列表，并标记指定歌曲是否已在各歌单中（用于收藏弹窗）。"""
    result = await playlist_service.list_user_playlists_with_music_membership(
        db, current_user.id, music_id
    )
    items = [
        {
            "id": item["playlist"].id,
            "title": item["playlist"].title,
            "is_private": item["playlist"].is_private,
            "is_like": item["playlist"].is_like,
            "cover_icon_url": item["playlist"].cover_icon_url,
            "contains_music": item["contains_music"],
        }
        for item in result["items"]
    ]
    return {"items": items, "total": result["total"]}


@router.get("/{playlist_id}", response_model=PlaylistOut)
async def get_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
):
    """获取歌单详情。

    仅允许查看自己的歌单或 `is_private=False` 的公开歌单。
    """
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    if playlist.is_private and playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this playlist",
        )

    collected = await collection_service.is_playlist_collected(
        db, current_user.id, playlist_id
    )
    return PlaylistOut.model_validate(playlist).model_copy(
        update={"is_collected_by_me": collected}
    )


@router.patch("/{playlist_id}", response_model=PlaylistOut)
async def update_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
    update_in: PlaylistUpdate,
):
    """修改歌单信息（仅文本字段，不含封面替换和标签编辑）。"""
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this playlist",
        )

    playlist = await playlist_service.update_playlist(
        db,
        playlist,
        title=update_in.title,
        description=update_in.description,
        is_private=update_in.is_private,
    )

    # 重新加载完整关联数据
    playlist = await playlist_service.get_playlist_by_id(db, playlist.id)
    return playlist


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
):
    """删除自己的歌单。"""
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this playlist",
        )

    await playlist_service.delete_playlist(db, playlist)


# ---------------------------------------------------------------------------
# 歌单内歌曲管理
# ---------------------------------------------------------------------------

@router.post(
    "/{playlist_id}/musics/{music_id}",
    response_model=PlaylistOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_music_to_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
    music_id: int,
):
    """添加一首已上架音乐到歌单。仅允许操作自己的歌单。"""
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this playlist",
        )

    await playlist_service.add_music_to_playlist(db, playlist_id, music_id)

    # 重新加载完整关联数据
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    return playlist


@router.delete(
    "/{playlist_id}/musics/{music_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_music_from_playlist(
    db: SessionDep,
    current_user: ActiveUser,
    playlist_id: int,
    music_id: int,
):
    """从歌单移除一首音乐。仅允许操作自己的歌单。"""
    playlist = await playlist_service.get_playlist_by_id(db, playlist_id)
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )

    if playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify this playlist",
        )

    await playlist_service.remove_music_from_playlist(db, playlist_id, music_id)
