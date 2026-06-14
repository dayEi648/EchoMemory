"""专辑相关 API 端点，提供管理员专辑管理接口与公开查询接口。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import AdminUser, OptionalUser, SessionDep
from echomemory_backend.api.helpers import (
    build_detail_response_from_schema,
    require_entity,
)
from echomemory_backend.api.v1.endpoints._upload_helpers import UploadCollector
from echomemory_backend.core.clients import oss_client
from echomemory_backend.models.album import Album
from echomemory_backend.schemas.album import (
    AdminAlbumListItem,
    AlbumOut,
    AlbumUpdate,
    PaginatedAdminAlbumListOut,
    PaginatedAlbumListOut,
)
from echomemory_backend.services import album_service, collection_service
from echomemory_backend.services.cache_service import (
    get_cached_album_detail,
    set_cached_album_detail,
)

router = APIRouter(prefix="/albums", tags=["albums"])

def _album_not_deleted(album: Album) -> bool:
    """判断专辑是否未删除。"""
    return not album.is_deleted


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.post("/admin", response_model=AlbumOut, status_code=HttpStatus.CREATED)
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
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover icon must be an image file",
        )
    if cover.content_type is None or not cover.content_type.startswith("image/"):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover must be an image file",
        )

    async with UploadCollector() as uploads:
        cover_icon_url = await oss_client.upload_image_to_oss(
            cover_icon.file, folder="album_covers", filename_prefix="icon"
        )
        uploads.add(cover_icon_url)

        cover_url = await oss_client.upload_image_to_oss(
            cover.file, folder="album_covers", filename_prefix="cover"
        )
        uploads.add(cover_url)

        album = await album_service.create_album(
            db,
            title=title,
            description=description,
            source=source,
            cover_icon_url=cover_icon_url,
            cover_url=cover_url,
            author_ids=author_ids or None,
        )

    # 重新加载完整关联数据
    album = await album_service.get_album_by_id(db, album.id)
    return album


@router.get("/admin/list", response_model=PaginatedAdminAlbumListOut)
async def admin_list_albums(
    db: SessionDep,
    _: AdminUser,
    q: str | None = Query(None, description="按标题模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """管理员列出所有专辑（含作者和歌曲数），支持标题搜索和分页。"""
    result = await album_service.admin_search_albums(
        db, q=q, limit=limit, offset=offset
    )
    items = [
        AdminAlbumListItem.model_validate(album).model_copy(
            update={"music_count": len(album.musics)}
        )
        for album in result["items"]
    ]
    return {"items": items, "total": result["total"]}


@router.patch("/admin/{album_id}", response_model=AlbumOut)
async def admin_update_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    update_in: AlbumUpdate,
):
    """管理员修改专辑信息（不含文件替换和标签编辑）。"""
    album = await require_entity(
        album_service.get_album_by_id,
        db,
        album_id,
        detail="Album not found",
        predicate=_album_not_deleted,
    )

    album = await album_service.update_album(
        db,
        album,
        title=update_in.title,
        description=update_in.description,
        source=update_in.source,
        author_ids=update_in.author_ids,
    )

    album = await album_service.get_album_by_id(db, album.id)
    return album


@router.patch("/admin/{album_id}/covers", response_model=AlbumOut)
async def admin_update_album_covers(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    cover_icon: UploadFile | None = File(None),
    cover: UploadFile | None = File(None),
):
    """管理员替换专辑封面图片。

    支持单独替换封面图标、封面大图，或同时替换两者。
    上传新图片到 OSS 后自动删除旧图片。
    """
    album = await require_entity(
        album_service.get_album_by_id,
        db,
        album_id,
        detail="Album not found",
        predicate=_album_not_deleted,
    )

    if cover_icon is None and cover is None:
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="At least one cover file must be provided",
        )

    if cover_icon is not None and (
        cover_icon.content_type is None or not cover_icon.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover icon must be an image file",
        )
    if cover is not None and (
        cover.content_type is None or not cover.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover must be an image file",
        )

    old_urls_to_delete: list[str] = []
    cover_icon_url: str | None = None
    cover_url: str | None = None

    async with UploadCollector() as uploads:
        if cover_icon is not None:
            cover_icon_url = await oss_client.upload_image_to_oss(
                cover_icon.file, folder="album_covers", filename_prefix="icon"
            )
            uploads.add(cover_icon_url)
            if album.cover_icon_url:
                old_urls_to_delete.append(album.cover_icon_url)

        if cover is not None:
            cover_url = await oss_client.upload_image_to_oss(
                cover.file, folder="album_covers", filename_prefix="cover"
            )
            uploads.add(cover_url)
            if album.cover_url:
                old_urls_to_delete.append(album.cover_url)

        album = await album_service.update_album_covers(
            db,
            album,
            cover_icon_url=cover_icon_url,
            cover_url=cover_url,
        )

    for old_url in old_urls_to_delete:
        await oss_client.delete_object_by_url(old_url)

    album = await album_service.get_album_by_id(db, album.id)
    return album


@router.delete("/admin/{album_id}", status_code=HttpStatus.NO_CONTENT)
async def admin_delete_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
):
    """管理员软删除专辑。"""
    album = await require_entity(
        album_service.get_album_by_id,
        db,
        album_id,
        detail="Album not found",
        predicate=_album_not_deleted,
    )

    await album_service.soft_delete_album(db, album)
    return None


@router.post(
    "/admin/{album_id}/musics/{music_id}",
    response_model=AlbumOut,
    status_code=HttpStatus.CREATED,
)
async def add_music_to_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    music_id: int,
):
    """将一首已上架音乐加入专辑。"""
    await require_entity(
        album_service.get_album_by_id,
        db,
        album_id,
        detail="Album not found",
        predicate=_album_not_deleted,
    )

    await album_service.add_music_to_album(db, album_id, music_id)

    album = await album_service.get_album_by_id(db, album_id)
    return album


@router.delete(
    "/admin/{album_id}/musics/{music_id}",
    status_code=HttpStatus.NO_CONTENT,
)
async def remove_music_from_album(
    db: SessionDep,
    _: AdminUser,
    album_id: int,
    music_id: int,
):
    """从专辑移除一首音乐。"""
    await require_entity(
        album_service.get_album_by_id,
        db,
        album_id,
        detail="Album not found",
        predicate=_album_not_deleted,
    )

    await album_service.remove_music_from_album(db, album_id, music_id)

    return None


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

# 注意：/search 必须排在 /{album_id} 之前，否则 FastAPI 会把 "search" 当作 album_id。
@router.get("/search", response_model=PaginatedAlbumListOut)
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


@router.get("/", response_model=PaginatedAlbumListOut)
async def list_albums(
    db: SessionDep,
    emotion_tag_id: int | None = Query(None),
    interest_tag_id: int | None = Query(None),
    q: str | None = Query(None, description="按标题模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出未删除专辑，支持标签筛选和标题搜索。"""
    return await album_service.list_albums(
        db,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{album_id}", response_model=AlbumOut)
async def get_album(
    db: SessionDep,
    album_id: int,
    current_user: OptionalUser = None,
):
    """获取未删除专辑的详情（优先命中 Redis 缓存）。"""
    album = await db.get(Album, album_id)
    if album is None or not _album_not_deleted(album):
        raise HTTPException(
            status_code=HttpStatus.NOT_FOUND, detail="Album not found"
        )

    cached = await get_cached_album_detail(album_id)
    if cached is None:
        album_full = await album_service.get_album_by_id(db, album_id)
        cached = AlbumOut.model_validate(album_full)
        await set_cached_album_detail(cached)

    return await build_detail_response_from_schema(
        cached,
        collection_service.is_album_collected,
        db,
        current_user,
        entity_id=album_id,
    )
