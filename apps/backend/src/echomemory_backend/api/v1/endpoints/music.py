"""音乐相关 API 端点，提供管理员导入/修改/上下架及公开搜索/列表/详情查询接口。"""

import os
import uuid
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.api.v1.endpoints._upload_helpers import upload_optional_image
from echomemory_backend.core import oss_client
from echomemory_backend.core.oss_client import _ALLOWED_AUDIO_TYPES
from echomemory_backend.schemas.music import (
    MusicOut,
    PaginatedAdminMusicListOut,
    PaginatedMusicListOut,
)
from echomemory_backend.core.redis_client import check_rate_limit
from echomemory_backend.services import music_service

router = APIRouter(prefix="/music", tags=["music"])


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

@router.post("/admin/import", response_model=MusicOut, status_code=status.HTTP_201_CREATED)
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
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many upload requests, please try again later",
        )

    # ----- 文件类型校验 -----
    if audio_file.content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid audio file type: {audio_file.content_type}",
        )

    if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cover icon must be an image file",
        )

    if cover_home is not None and (
        cover_home.content_type is None or not cover_home.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cover home must be an image file",
        )

    if cover_play is not None and (
        cover_play.content_type is None or not cover_play.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cover play must be an image file",
        )

    # ----- 日期解析 -----
    release_date_parsed: date | None = None
    if release_date:
        try:
            release_date_parsed = date.fromisoformat(release_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="release_date must be in YYYY-MM-DD format",
            ) from exc

    # ----- 上传文件到 OSS（带孤儿文件清理） -----
    uploaded_urls: list[str] = []
    file_prefix = uuid.uuid4().hex[:12]
    try:
        file_url = await oss_client.upload_audio_to_oss(
            audio_file.file,
            prefix=file_prefix,
            ext=_safe_ext(audio_file.filename, "mp3"),
        )
        uploaded_urls.append(file_url)

        cover_icon_url = await oss_client.upload_image_to_oss(
            cover_icon.file,
            folder="music_covers",
            filename_prefix="icon",
        )
        uploaded_urls.append(cover_icon_url)

        cover_home_url = await upload_optional_image(cover_home, "music_covers", "home")
        if cover_home_url:
            uploaded_urls.append(cover_home_url)

        cover_play_url = await upload_optional_image(cover_play, "music_covers", "play")
        if cover_play_url:
            uploaded_urls.append(cover_play_url)

        lyrics_url: str | None = None
        if lyrics_file is not None:
            lyrics_url = await oss_client.upload_lyrics_to_oss(
                lyrics_file.file,
                prefix=file_prefix,
                ext=_safe_ext(lyrics_file.filename, "lrc"),
            )
            uploaded_urls.append(lyrics_url)

        # ----- 创建数据库记录 -----
        music = await music_service.create_music(
            db,
            title=title,
            is_vip=is_vip,
            source=source or None,
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
    except HTTPException:
        for url in uploaded_urls:
            await oss_client.delete_object_by_url(url)
        raise
    except (RuntimeError, ValueError, IntegrityError, SQLAlchemyError):
        # 任何其他异常（OSS 上传失败或数据库失败），清理已上传的 OSS 文件
        for url in uploaded_urls:
            await oss_client.delete_object_by_url(url)
        raise

    # 重新加载完整关联数据以匹配 MusicOut（避免异步懒加载 MissingGreenlet）
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.patch("/admin/{music_id}", response_model=MusicOut)
async def admin_update_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
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
    music = await music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )

    # ----- 日期解析 -----
    release_date_parsed: date | None = None
    if release_date:
        try:
            release_date_parsed = date.fromisoformat(release_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    try:
        if audio_file is not None:
            if audio_file.content_type not in _ALLOWED_AUDIO_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Invalid audio file type: {audio_file.content_type}",
                )
            new_file_url = await oss_client.upload_audio_to_oss(
                audio_file.file,
                prefix=file_prefix,
                ext=_safe_ext(audio_file.filename, "mp3"),
            )
            if music.file_url:
                old_urls_to_delete.append(music.file_url)

        if cover_icon is not None:
            if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Cover icon must be an image file",
                )
            new_cover_icon_url = await oss_client.upload_image_to_oss(
                cover_icon.file, folder="music_covers", filename_prefix="icon"
            )
            if music.cover_icon_url:
                old_urls_to_delete.append(music.cover_icon_url)

        if cover_home is not None:
            new_cover_home_url = await upload_optional_image(cover_home, "music_covers", "home")
            if new_cover_home_url and music.cover_home_url:
                old_urls_to_delete.append(music.cover_home_url)

        if cover_play is not None:
            new_cover_play_url = await upload_optional_image(cover_play, "music_covers", "play")
            if new_cover_play_url and music.cover_play_url:
                old_urls_to_delete.append(music.cover_play_url)

        if lyrics_file is not None:
            new_lyrics_url = await oss_client.upload_lyrics_to_oss(
                lyrics_file.file,
                prefix=file_prefix,
                ext=_safe_ext(lyrics_file.filename, "lrc"),
            )
            if music.lyrics_url:
                old_urls_to_delete.append(music.lyrics_url)
    except HTTPException:
        # 上传失败时清理已上传的新文件
        for url in [new_file_url, new_cover_icon_url, new_cover_home_url, new_cover_play_url, new_lyrics_url]:
            if url:
                await oss_client.delete_object_by_url(url)
        raise

    # ----- 更新数据库 -----
    music = await music_service.update_music(
        db,
        music,
        title=title,
        is_vip=is_vip,
        source=source or None,
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

    # 更新成功后删除旧文件
    for url in old_urls_to_delete:
        await oss_client.delete_object_by_url(url)

    # 重新加载完整关联数据以匹配 MusicOut
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/publish", response_model=MusicOut)
async def admin_publish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
):
    """管理员上架音乐。"""
    music = await music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    music = await music_service.set_music_published(db, music, published=True)
    music = await music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/unpublish", response_model=MusicOut)
async def admin_unpublish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
):
    """管理员下架音乐。"""
    music = await music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """管理员列出所有音乐（含未上架），支持搜索和多条件筛选。"""
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
        limit=limit,
        offset=offset,
    )


@router.get("/admin/{music_id}", response_model=MusicOut)
async def admin_get_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
):
    """管理员获取任意音乐详情（含未上架）。"""
    music = await music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    return music


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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出已上架音乐，支持筛选。"""
    return await music_service.list_musics(
        db,
        style_id=style_id,
        language_id=language_id,
        is_vip=is_vip,
        limit=limit,
        offset=offset,
    )


@router.get("/{music_id}", response_model=MusicOut)
async def get_music(
    db: SessionDep,
    music_id: int,
):
    """获取已上架音乐的详情。"""
    music = await music_service.get_music_by_id(db, music_id)
    if music is None or not music.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    return music
