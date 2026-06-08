from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.core import oss_client
from echomemory_backend.schemas.album import (
    AlbumCreate,
    AlbumListOut,
    AlbumOut,
    AlbumUpdate,
)
from echomemory_backend.services import album_service
from echomemory_backend.services.user_service import BusinessError

router = APIRouter(prefix="/albums", tags=["albums"])


async def _upload_optional_image(
    file: UploadFile | None, folder: str, prefix: str
) -> str | None:
    """上传可选图片文件到 OSS，失败时抛出 HTTPException。"""
    if file is None:
        return None
    if file.content_type is None or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{prefix} must be an image file",
        )
    try:
        return await oss_client.upload_image_to_oss(
            file.file, folder=folder, filename_prefix=prefix
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.post("/admin", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
async def create_album(
    db: SessionDep,
    _: AdminUser,
    title: str = Form(..., min_length=1, max_length=128),
    description: str | None = Form(None, max_length=500),
    source: str | None = Form(None, max_length=50),
    cover_icon: UploadFile = File(...),
    cover: UploadFile = File(...),
    author_ids: list[int] = Form([]),
):
    """管理员创建专辑。

    封面图片通过上传方式提供，服务端自动上传到 OSS 并生成 URL。
    标签由系统根据歌曲收藏自动计算，不允许手动编辑。
    """
    # 文件类型校验
    if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cover icon must be an image file",
        )
    if cover.content_type is None or not cover.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cover must be an image file",
        )

    uploaded_urls: list[str] = []
    try:
        cover_icon_url = await oss_client.upload_image_to_oss(
            cover_icon.file, folder="album_covers", filename_prefix="icon"
        )
        uploaded_urls.append(cover_icon_url)

        cover_url = await oss_client.upload_image_to_oss(
            cover.file, folder="album_covers", filename_prefix="cover"
        )
        uploaded_urls.append(cover_url)

        album = await album_service.create_album(
            db,
            title=title,
            description=description,
            source=source,
            cover_icon_url=cover_icon_url,
            cover_url=cover_url,
            author_ids=author_ids or None,
        )
    except HTTPException:
        raise
    except BusinessError as exc:
        # 业务校验失败时清理已上传 OSS 文件
        for url in uploaded_urls:
            await oss_client.delete_object_by_url(url)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception:
        for url in uploaded_urls:
            await oss_client.delete_object_by_url(url)
        raise

    # 重新加载完整关联数据
    album = await album_service.get_album_by_id(db, album.id)
    return album


@router.patch("/admin/{album_id}", response_model=AlbumOut)
async def admin_update_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    update_in: AlbumUpdate,
):
    """管理员修改专辑信息（不含文件替换和标签编辑）。"""
    album = await album_service.get_album_by_id(db, album_id)
    if album is None or album.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )

    try:
        album = await album_service.update_album(
            db,
            album,
            title=update_in.title,
            description=update_in.description,
            source=update_in.source,
            author_ids=update_in.author_ids,
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    album = await album_service.get_album_by_id(db, album.id)
    return album


@router.delete("/admin/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
):
    """管理员软删除专辑。"""
    album = await album_service.get_album_by_id(db, album_id)
    if album is None or album.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )

    await album_service.soft_delete_album(db, album)
    return None


@router.post(
    "/admin/{album_id}/musics/{music_id}",
    response_model=AlbumOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_music_to_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    music_id: int,
):
    """将一首已上架音乐加入专辑。"""
    album = await album_service.get_album_by_id(db, album_id)
    if album is None or album.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )

    try:
        await album_service.add_music_to_album(db, album_id, music_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    album = await album_service.get_album_by_id(db, album_id)
    return album


@router.delete(
    "/admin/{album_id}/musics/{music_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_music_from_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    music_id: int,
):
    """从专辑移除一首音乐。"""
    album = await album_service.get_album_by_id(db, album_id)
    if album is None or album.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )

    try:
        await album_service.remove_music_from_album(db, album_id, music_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return None


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

# 注意：/search 必须排在 /{album_id} 之前，否则 FastAPI 会把 "search" 当作 album_id。
@router.get("/search", response_model=list[AlbumListOut])
async def search_albums(
    db: SessionDep,
    q: str | None = Query(None, description="按标题模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """按标题模糊搜索未删除专辑。"""
    return await album_service.search_albums(
        db, q=q, limit=limit, offset=offset
    )


@router.get("/", response_model=list[AlbumListOut])
async def list_albums(
    db: SessionDep,
    emotion_tag_id: int | None = Query(None),
    interest_tag_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出未删除专辑，支持标签筛选。"""
    return await album_service.list_albums(
        db,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{album_id}", response_model=AlbumOut)
async def get_album(
    db: SessionDep,
    album_id: int,
):
    """获取未删除专辑的详情。"""
    album = await album_service.get_album_by_id(db, album_id)
    if album is None or album.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )
    return album
