"""管理员音乐知识库管理 API。

允许管理员上传 .docx/.pdf/.md 文档，解析后切分并写入向量库；
同时支持按文档 source 列出与删除。
"""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, File, Query, UploadFile

from echomemory_backend.api.deps import AdminUser, SessionDep
from echomemory_backend.core.exceptions.business import BusinessError
from echomemory_backend.core.exceptions.codes import ErrorCode
from echomemory_backend.rag.document_parser import is_supported_file_type
from echomemory_backend.schemas.music_knowledge import (
    MusicKnowledgeDeleteOut,
    MusicKnowledgeIngestOut,
    MusicKnowledgeSourceListOut,
    MusicKnowledgeSourceParams,
)
from echomemory_backend.services import music_knowledge_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/music-knowledge",
    tags=["admin-music-knowledge"],
)

_MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_upload_file(file: UploadFile) -> None:
    """校验上传文件类型与大小。

    异常:
        BusinessError: 文件类型不支持或超出大小时抛出。
    """
    if file.filename is None or not is_supported_file_type(file.filename):
        raise BusinessError(
            "仅支持 .docx、.pdf、.md、.markdown 文件",
            code=ErrorCode.CLIENT_MUSIC_KNOWLEDGE_UNSUPPORTED_FILE_TYPE,
        )

    if file.size is not None and file.size > _MAX_DOCUMENT_SIZE_BYTES:
        raise BusinessError(
            f"文件大小超过 {_MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)} MB 限制",
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        )


@router.post(
    "/documents",
    response_model=MusicKnowledgeIngestOut,
)
async def admin_upload_music_knowledge_document(
    db: SessionDep,
    _: AdminUser,
    file: Annotated[UploadFile, File(...)],
) -> MusicKnowledgeIngestOut:
    """上传音乐知识库文档并解析入库。

    同名文档会覆盖旧数据。
    """
    _validate_upload_file(file)

    try:
        result = await music_knowledge_service.ingest_document(
            db,
            filename=file.filename or "unknown",
            file=file.file,
        )
    except ValueError as exc:
        logger.warning("Failed to ingest music knowledge document: %s", exc)
        raise BusinessError(
            str(exc),
            code=ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS,
        ) from exc
    except Exception as exc:
        logger.exception("Failed to ingest music knowledge document")
        raise BusinessError(
            "文档入库失败",
            code=ErrorCode.SYSTEM_MUSIC_KNOWLEDGE_INGEST_FAILED,
        ) from exc

    return MusicKnowledgeIngestOut(
        source=result.source,
        chunk_count=result.chunk_count,
    )


@router.get(
    "/documents",
    response_model=MusicKnowledgeSourceListOut,
)
async def admin_list_music_knowledge_documents(
    db: SessionDep,
    _: AdminUser,
    params: Annotated[MusicKnowledgeSourceParams, Query()],
) -> MusicKnowledgeSourceListOut:
    """列出已入库的音乐知识库文档 source 列表。"""
    items, total = await music_knowledge_service.list_sources(
        db,
        limit=params.limit,
        offset=params.offset,
    )
    return MusicKnowledgeSourceListOut(items=items, total=total)


@router.delete(
    "/documents/{source}",
    response_model=MusicKnowledgeDeleteOut,
)
async def admin_delete_music_knowledge_document(
    db: SessionDep,
    _: AdminUser,
    source: str,
) -> MusicKnowledgeDeleteOut:
    """删除指定 source 的音乐知识库文档（即删除其全部向量片段）。"""
    decoded_source = unquote(source)
    deleted = await music_knowledge_service.delete_by_source(db, decoded_source)
    await db.commit()

    if deleted == 0:
        raise BusinessError(
            "文档不存在",
            code=ErrorCode.MUSIC_KNOWLEDGE_SOURCE_NOT_FOUND,
        )

    return MusicKnowledgeDeleteOut(deleted_chunks=deleted)
