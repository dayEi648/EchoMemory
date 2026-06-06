import os
from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.core import oss_client
from echomemory_backend.schemas.music import MusicListOut, MusicOut, MusicUpdate
from echomemory_backend.services import music_service
from echomemory_backend.services.user_service import BusinessError

router = APIRouter(prefix="/music", tags=["music"])

_ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/flac",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/aac",
}


def _safe_ext(filename: str | None, default: str) -> str:
    """从上传文件名中安全地提取扩展名。"""
    if not filename:
        return default
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    return ext if ext else default


# ---------------------------------------------------------------------------
# 管理员接口
# ---------------------------------------------------------------------------

@router.post("/admin/import", response_model=MusicOut, status_code=status.HTTP_201_CREATED)
def import_music(
    db: SessionDep,
    _: AdminUser,
    title: str = Form(..., min_length=1, max_length=128),
    audio_file: UploadFile = File(...),
    cover_icon: UploadFile = File(...),
    is_vip: bool = Form(False),
    source: str | None = Form(None, max_length=50),
    style_id: int | None = Form(None),
    language_id: int | None = Form(None),
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

    所有文件均通过上传方式提供，服务端自动上传到 OSS 并生成 URL。
    禁止直接填写任何 URL 字符串。
    """
    # ----- 文件类型校验 -----
    if audio_file.content_type not in _ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid audio file type: {audio_file.content_type}",
        )

    if cover_icon.content_type is None or not cover_icon.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cover icon must be an image file",
        )

    if cover_home is not None and (
        cover_home.content_type is None or not cover_home.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cover home must be an image file",
        )

    if cover_play is not None and (
        cover_play.content_type is None or not cover_play.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cover play must be an image file",
        )

    # ----- 日期解析 -----
    release_date_parsed: date | None = None
    if release_date:
        try:
            release_date_parsed = date.fromisoformat(release_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="release_date must be in YYYY-MM-DD format",
            ) from exc

    # ----- 上传必填文件 -----
    try:
        file_url = oss_client.upload_audio_to_oss(
            audio_file.file,
            ext=_safe_ext(audio_file.filename, "mp3"),
        )
        cover_icon_url = oss_client.upload_image_to_oss(
            cover_icon.file,
            folder="music_covers",
            filename_prefix="icon",
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    # ----- 上传选填文件 -----
    cover_home_url: str | None = None
    if cover_home is not None:
        try:
            cover_home_url = oss_client.upload_image_to_oss(
                cover_home.file,
                folder="music_covers",
                filename_prefix="home",
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

    cover_play_url: str | None = None
    if cover_play is not None:
        try:
            cover_play_url = oss_client.upload_image_to_oss(
                cover_play.file,
                folder="music_covers",
                filename_prefix="play",
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

    lyrics_url: str | None = None
    if lyrics_file is not None:
        try:
            lyrics_url = oss_client.upload_lyrics_to_oss(
                lyrics_file.file,
                ext=_safe_ext(lyrics_file.filename, "lrc"),
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

    # ----- 创建数据库记录 -----
    try:
        music = music_service.create_music(
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
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    return music


@router.patch("/admin/{music_id}", response_model=MusicOut)
def admin_update_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
    update_in: MusicUpdate,
):
    """管理员修改音乐信息（不含文件替换）。"""
    music = music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )

    try:
        music = music_service.update_music(
            db,
            music,
            title=update_in.title,
            is_vip=update_in.is_vip,
            source=update_in.source,
            style_id=update_in.style_id,
            language_id=update_in.language_id,
            release_date=update_in.release_date,
            author_ids=update_in.author_ids,
            instrument_ids=update_in.instrument_ids,
            emotion_tag_ids=update_in.emotion_tag_ids,
            interest_tag_ids=update_in.interest_tag_ids,
        )
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    # 重新加载完整关联数据以匹配 MusicOut
    music = music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/publish", response_model=MusicOut)
def admin_publish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
):
    """管理员上架音乐。"""
    music = music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    music = music_service.set_music_published(db, music, published=True)
    music = music_service.get_music_by_id(db, music.id)
    return music


@router.post("/admin/{music_id}/unpublish", response_model=MusicOut)
def admin_unpublish_music(
    db: SessionDep,
    _: AdminUser,
    music_id: int,
):
    """管理员下架音乐。"""
    music = music_service.get_music_by_id(db, music_id)
    if music is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    music = music_service.set_music_published(db, music, published=False)
    music = music_service.get_music_by_id(db, music.id)
    return music


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

# 注意：/search 必须排在 /{music_id} 之前，否则 FastAPI 会把 "search" 当作 music_id。
@router.get("/search", response_model=list[MusicListOut])
def search_musics(
    db: SessionDep,
    q: str | None = Query(None, description="按标题模糊搜索"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """按标题模糊搜索已上架音乐。"""
    return music_service.search_musics(
        db, q=q, limit=limit, offset=offset
    )


@router.get("/", response_model=list[MusicListOut])
def list_musics(
    db: SessionDep,
    style_id: int | None = Query(None),
    language_id: int | None = Query(None),
    is_vip: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """分页列出已上架音乐，支持筛选。"""
    return music_service.list_musics(
        db,
        style_id=style_id,
        language_id=language_id,
        is_vip=is_vip,
        limit=limit,
        offset=offset,
    )


@router.get("/{music_id}", response_model=MusicOut)
def get_music(
    db: SessionDep,
    music_id: int,
):
    """获取已上架音乐的详情。"""
    music = music_service.get_music_by_id(db, music_id)
    if music is None or not music.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Music not found"
        )
    return music
