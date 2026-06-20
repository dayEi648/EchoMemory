"""音乐相关 API 端点，提供管理员导入/修改/上下架及公开搜索/列表/详情查询接口。"""
from echomemory_backend.core.exceptions.codes import ErrorCode, HttpStatus

import os
import uuid
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import AdminUser, OptionalUser, PositiveIntPath, SessionDep
from echomemory_backend.api.helpers import (
    build_detail_response_from_schema,
    require_entity,
)
from echomemory_backend.api.v1.endpoints._upload_helpers import (
    UploadCollector,
    upload_optional_image,
)
from echomemory_backend.core.clients import oss_client
from echomemory_backend.core.clients.oss_client import _ALLOWED_AUDIO_TYPES
from echomemory_backend.models.music import Music
from echomemory_backend.schemas.music import (
    LyricsOut,
    MusicOut,
    PaginatedAdminMusicListOut,
    PaginatedMusicListOut,
)
from echomemory_backend.core.clients.redis_client import check_rate_limit
from echomemory_backend.services import collection_service, music_service
from echomemory_backend.services.cache_service import (
    get_cached_music_detail,
    set_cached_music_detail,
)

router = APIRouter(prefix="/music", tags=["music"])

def _music_published(music: Music) -> bool:
    """判断音乐是否已上架。"""
    return music.is_published


_ALLOWED_FILE_EXTS = {"mp3", "flac", "wav", "ogg", "aac", "lrc", "jpg", "jpeg", "png"}


def _safe_ext(filename: str | None, default: str) -> str:
    """从上传文件名中安全地提取扩展名，不在白名单时回退到默认值。"""
    if not filename:
        return default
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    return ext if ext in _ALLOWED_FILE_EXTS else default


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.post("/admin/import", response_model=MusicOut, status_code=HttpStatus.CREATED)
async def import_music(
    db: SessionDep,
    admin: AdminUser,
    title: str = Form(..., min_length=1, max_length=128),
    audio_file: UploadFile = File(...),
    cover_icon: UploadFile = File(...),
    is_vip: bool = Form(False),
    source: str | None = Form(None, max_length=50),
    style_id: int | None = Form(None, gt=0),
    language_id: int | None = Form(None, gt=0),
    release_date: str | None = Form(None, description="格式: YYYY-MM-DD"),
    author_ids: list[int] = Form([]),
    instrument_ids: list[int] = Form([]),
    emotion_tag_ids: list[int] = Form([]),
    interest_tag_ids: list[int] = Form([]),
    cover_home: UploadFile | None = File(None),
    cover_play: UploadFile | None = File(None),
    lyrics_file: UploadFile | None = File(None),
):
    """管理员导入音乐。

    同一管理员 1 小时内最多允许 10 次导入请求。

    所有文件均通过上传方式提供，服务端自动上传到 OSS 并生成 URL。
    禁止直接填写任何 URL 字符串。
    """
    # ----- 频率限制 -----
    if not await check_rate_limit(
        f"upload_music:{admin.id}", max_requests=10, window_seconds=3600
    ):
        raise HTTPException(
            status_code=HttpStatus.TOO_MANY_REQUESTS,
            detail="Too many upload requests, please try again later",
        )

    # ----- 文件类型校验 -----
    if audio_file.content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail=f"Invalid audio file type: {audio_file.content_type}",
        )

    if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover icon must be an image file",
        )

    if cover_home is not None and (
        cover_home.content_type is None or not cover_home.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover home must be an image file",
        )

    if cover_play is not None and (
        cover_play.content_type is None or not cover_play.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=HttpStatus.UNPROCESSABLE_ENTITY,
            detail="Cover play must be an image file",
        )

    # ----- 日期解析 -----
    release_date_parsed: date | None = None
    if release_date:
        try:
            release_date_parsed = date.fromisoformat(release_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                detail="release_date must be in YYYY-MM-DD format",
            ) from exc

    file_prefix = uuid.uuid4().hex[:12]
    async with UploadCollector() as uploads:
        file_url = await oss_client.upload_audio_to_oss(
            audio_file.file,
            prefix=file_prefix,
            ext=_safe_ext(audio_file.filename, "mp3"),
        )
        uploads.add(file_url)

        cover_icon_url = await oss_client.upload_image_to_oss(
            cover_icon.file,
            folder="music_covers",
            filename_prefix="icon",
        )
        uploads.add(cover_icon_url)

        cover_home_url = await upload_optional_image(cover_home, "music_covers", "home")
        uploads.add(cover_home_url)

        cover_play_url = await upload_optional_image(cover_play, "music_covers", "play")
        uploads.add(cover_play_url)

        lyrics_url: str | None = None
        if lyrics_file is not None:
            lyrics_url = await oss_client.upload_lyrics_to_oss(
                lyrics_file.file,
                prefix=file_prefix,
                ext=_safe_ext(lyrics_file.filename, "lrc"),
            )
            uploads.add(lyrics_url)

        music = await music_service.create_music(
            db,
            title=title,
            is_vip=is_vip,
            source=source,
            style_id=style_id,
            language_id=language_id,
            release_date=release_date_parsed,
            author_ids=author_ids or None,
            instrument_ids=instrument_ids or None,
            emotion_tag_ids=emotion_tag_ids or None,
            interest_tag_ids=interest_tag_ids or None,
            file_url=file_url,
            lyrics_url=lyrics_url,
            cover_icon_url=cover_icon_url,
            cover_home_url=cover_home_url,
            cover_play_url=cover_play_url,
        )

    # 重新加载完整关联数据以匹配 MusicOut（避免异步懒加载 MissingGreenlet）
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.patch("/admin/{music_id}", response_model=MusicOut)
async def admin_update_music(
    db: SessionDep,
    _: AdminUser,
    music_id: PositiveIntPath,
    title: str | None = Form(None, min_length=1, max_length=128),
    source: str | None = Form(None, max_length=50),
    style_id: int | None = Form(None, gt=0),
    language_id: int | None = Form(None, gt=0),
    release_date: str | None = Form(None, description="格式: YYYY-MM-DD"),
    is_vip: bool | None = Form(None),
    author_ids: list[int] | None = Form(None),
    instrument_ids: list[int] | None = Form(None),
    emotion_tag_ids: list[int] | None = Form(None),
    interest_tag_ids: list[int] | None = Form(None),
    audio_file: UploadFile | None = File(None),
    cover_icon: UploadFile | None = File(None),
    cover_home: UploadFile | None = File(None),
    cover_play: UploadFile | None = File(None),
    lyrics_file: UploadFile | None = File(None),
):
    """管理员修改音乐信息（含可选文件替换）。"""
    music = await require_entity(
        music_service.get_music_by_id,
        db,
        music_id,
        detail="Music not found",
    )

    # ----- 日期解析 -----
    release_date_parsed: date | None = None
    if release_date:
        try:
            release_date_parsed = date.fromisoformat(release_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                detail="release_date must be in YYYY-MM-DD format",
            ) from exc

    # ----- 记录旧文件 URL（用于后续删除）-----
    old_urls_to_delete: list[str] = []

    # ----- 上传新文件（如有）-----
    new_file_url: str | None = None
    new_cover_icon_url: str | None = None
    new_cover_home_url: str | None = None
    new_cover_play_url: str | None = None
    new_lyrics_url: str | None = None

    file_prefix = uuid.uuid4().hex[:12]
    async with UploadCollector() as uploads:
        if audio_file is not None:
            if audio_file.content_type not in _ALLOWED_AUDIO_TYPES:
                raise HTTPException(
                    status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                    detail=f"Invalid audio file type: {audio_file.content_type}",
                )
            new_file_url = await oss_client.upload_audio_to_oss(
                audio_file.file,
                prefix=file_prefix,
                ext=_safe_ext(audio_file.filename, "mp3"),
            )
            uploads.add(new_file_url)
            if music.file_url:
                old_urls_to_delete.append(music.file_url)

        if cover_icon is not None:
            if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                    detail="Cover icon must be an image file",
                )
            new_cover_icon_url = await oss_client.upload_image_to_oss(
                cover_icon.file, folder="music_covers", filename_prefix="icon"
            )
            uploads.add(new_cover_icon_url)
            if music.cover_icon_url:
                old_urls_to_delete.append(music.cover_icon_url)

        if cover_home is not None:
            new_cover_home_url = await upload_optional_image(cover_home, "music_covers", "home")
            uploads.add(new_cover_home_url)
            if new_cover_home_url and music.cover_home_url:
                old_urls_to_delete.append(music.cover_home_url)

        if cover_play is not None:
            new_cover_play_url = await upload_optional_image(cover_play, "music_covers", "play")
            uploads.add(new_cover_play_url)
            if new_cover_play_url and music.cover_play_url:
                old_urls_to_delete.append(music.cover_play_url)

        if lyrics_file is not None:
            new_lyrics_url = await oss_client.upload_lyrics_to_oss(
                lyrics_file.file,
                prefix=file_prefix,
                ext=_safe_ext(lyrics_file.filename, "lrc"),
            )
            uploads.add(new_lyrics_url)
            if music.lyrics_url:
                old_urls_to_delete.append(music.lyrics_url)

        music = await music_service.update_music(
            db,
            music,
            title=title,
            is_vip=is_vip,
            source=source,
            style_id=style_id,
            language_id=language_id,
            release_date=release_date_parsed,
            author_ids=author_ids or None,
            instrument_ids=instrument_ids or None,
            emotion_tag_ids=emotion_tag_ids or None,
            interest_tag_ids=interest_tag_ids or None,
            file_url=new_file_url,
            lyrics_url=new_lyrics_url,
            cover_icon_url=new_cover_icon_url,
            cover_home_url=new_cover_home_url,
            cover_play_url=new_cover_play_url,
        )

    for url in old_urls_to_delete:
        await oss_client.delete_object_by_url(url)

    # 重新加载完整关联数据以匹配 MusicOut
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/publish", response_model=MusicOut)
async def admin_publish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: PositiveIntPath,
):
    """管理员上架音乐。"""
    music = await require_entity(
        music_service.get_music_by_id,
        db,
        music_id,
        detail="Music not found",
    )
    music = await music_service.set_music_published(db, music, published=True)
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/unpublish", response_model=MusicOut)
async def admin_unpublish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: PositiveIntPath,
):
    """管理员下架音乐。"""
    music = await require_entity(
        music_service.get_music_by_id,
        db,
        music_id,
        detail="Music not found",
    )
    music = await music_service.set_music_published(db, music, published=False)
    music = await music_service.get_music_by_id(db, music.id)
    return music


# 注意：/admin/list 必须排在 /admin/{music_id} 之前，否则 FastAPI 会把 "list" 当作 music_id。
@router.get("/admin/list", response_model=PaginatedAdminMusicListOut)
async def admin_list_music(
    db: SessionDep,
    _: AdminUser,
    q: str | None = Query(None, description="按标题模糊搜索"),
    style_id: int | None = Query(None),
    language_id: int | None = Query(None),
    is_vip: bool | None = Query(None),
    is_published: bool | None = Query(None, description="按上架状态筛选，None 表示不筛选"),
    instrument_id: int | None = Query(None),
    emotion_tag_id: int | None = Query(None),
    interest_tag_id: int | None = Query(None),
    sort_by: str = Query("id", description="排序字段: id / hot / play_count / created_at"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """管理员列出所有音乐（含未上架），支持搜索、多条件筛选与排序。"""
    return await music_service.admin_search_musics(
        db,
        q=q,
        style_id=style_id,
        language_id=language_id,
        is_vip=is_vip,
        is_published=is_published,
        instrument_id=instrument_id,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@router.get("/admin/{music_id}", response_model=MusicOut)
async def admin_get_music(
    db: SessionDep,
    _: AdminUser,
    music_id: PositiveIntPath,
):
    """管理员获取任意音乐详情（含未上架）。"""
    return await require_entity(
        music_service.get_music_by_id,
        db,
        music_id,
        detail="Music not found",
    )


@router.post("/admin/recalculate-hot")
async def admin_recalculate_hot(
    db: SessionDep,
    _: AdminUser,
):
    """管理员手动触发全量热度重算。"""
    from echomemory_backend.services.hotness_service import recalculate_all_hot

    result = await recalculate_all_hot(db)
    return result


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

# 注意：/search 必须排在 /{music_id} 之前，否则 FastAPI 会把 "search" 当作 music_id。
@router.get("/search", response_model=PaginatedMusicListOut)
async def search_musics(
    db: SessionDep,
    q: str | None = Query(None, description="按标题模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """按标题模糊搜索已上架音乐。"""
    return await music_service.search_musics(
        db, q=q, limit=limit, offset=offset
    )


@router.get("/", response_model=PaginatedMusicListOut)
async def list_musics(
    db: SessionDep,
    style_id: int | None = Query(None),
    language_id: int | None = Query(None),
    is_vip: bool | None = Query(None),
    instrument_id: int | None = Query(None, description="按乐器 ID 筛选"),
    emotion_tag_id: int | None = Query(None, description="按情绪标签 ID 筛选"),
    interest_tag_id: int | None = Query(None, description="按兴趣标签 ID 筛选"),
    release_date_from: str | None = Query(None, description="发行日期起始 (YYYY-MM-DD)"),
    release_date_to: str | None = Query(None, description="发行日期截止 (YYYY-MM-DD)"),
    q: str | None = Query(None, description="按标题模糊搜索"),
    sort_by: str = Query("created_at", description="排序字段: created_at / play_count / hot"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出已上架音乐，支持多条件筛选与排序。"""
    release_date_from_parsed: date | None = None
    release_date_to_parsed: date | None = None
    if release_date_from:
        try:
            release_date_from_parsed = date.fromisoformat(release_date_from)
        except ValueError as exc:
            raise HTTPException(
                status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                detail="release_date_from must be in YYYY-MM-DD format",
            ) from exc
    if release_date_to:
        try:
            release_date_to_parsed = date.fromisoformat(release_date_to)
        except ValueError as exc:
            raise HTTPException(
                status_code=HttpStatus.UNPROCESSABLE_ENTITY,
                detail="release_date_to must be in YYYY-MM-DD format",
            ) from exc

    return await music_service.list_musics(
        db,
        style_id=style_id,
        language_id=language_id,
        is_vip=is_vip,
        instrument_id=instrument_id,
        emotion_tag_id=emotion_tag_id,
        interest_tag_id=interest_tag_id,
        release_date_from=release_date_from_parsed,
        release_date_to=release_date_to_parsed,
        q=q,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )


@router.get("/{music_id}/lyrics", response_model=LyricsOut)
async def get_music_lyrics(
    db: SessionDep,
    music_id: PositiveIntPath,
):
    """获取已上架音乐的歌词文本，由后端从 OSS 拉取后返回给前端。"""
    music = await require_entity(
        music_service.get_music_by_id,
        db,
        music_id,
        detail="Music not found",
        predicate=_music_published,
    )
    if not music.lyrics_url:
        raise HTTPException(
            status_code=HttpStatus.NOT_FOUND, detail="Lyrics not found"
        )
    try:
        content_bytes = await oss_client.get_lyrics_content_by_url(music.lyrics_url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=HttpStatus.BAD_GATEWAY,
            detail="Failed to load lyrics",
        ) from exc
    return LyricsOut(content=content_bytes.decode("utf-8"))


@router.get("/{music_id}", response_model=MusicOut)
async def get_music(
    db: SessionDep,
    music_id: PositiveIntPath,
    current_user: OptionalUser = None,
):
    """获取已上架音乐的详情（优先命中 Redis 缓存）。"""
    music = await db.get(Music, music_id)
    if music is None or not _music_published(music):
        raise HTTPException(
            status_code=HttpStatus.NOT_FOUND, detail="Music not found"
        )

    cached = await get_cached_music_detail(music_id)
    if cached is None:
        music_full = await music_service.get_music_by_id(db, music_id)
        cached = MusicOut.model_validate(music_full)
        await set_cached_music_detail(cached)

    return await build_detail_response_from_schema(
        cached,
        collection_service.is_music_collected,
        db,
        current_user,
        entity_id=music_id,
    )
