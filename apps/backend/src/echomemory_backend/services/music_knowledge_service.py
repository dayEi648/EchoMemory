"""音乐知识库业务服务。

负责将管理员上传的文档解析、切分、嵌入后写入向量库，
并提供按文档 source 维度的列表与删除能力。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, BinaryIO

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.config import settings
from echomemory_backend.models.vector_document import VectorDocument
from echomemory_backend.rag.document_parser import parse_document
from echomemory_backend.rag.embeddings import EmbeddingClient
from echomemory_backend.rag.text_splitter import TextSplitter
from echomemory_backend.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)

MUSIC_KNOWLEDGE_NAMESPACE = "music_knowledge"

# 文档解析后的默认切分参数，可在配置中覆盖。
_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 100


@dataclass
class IngestResult:
    """文档入库结果。"""

    source: str
    chunk_count: int


def _normalize_source(filename: str) -> str:
    """移除路径信息，仅保留文件名作为 source 标识。"""
    return os.path.basename(filename)


def _file_extension(filename: str) -> str:
    """返回小写扩展名。"""
    lower = filename.lower()
    if lower.endswith(".markdown"):
        return "markdown"
    ext = os.path.splitext(filename)[1].lstrip(".")
    return ext.lower() or "unknown"


def _build_metas(source: str, file_type: str, total_chunks: int) -> list[dict[str, Any]]:
    """为每个 chunk 构造业务元数据。"""
    return [
        {
            "source": source,
            "file_type": file_type,
            "chunk_index": index,
            "total_chunks": total_chunks,
        }
        for index in range(total_chunks)
    ]


def _get_splitter() -> TextSplitter:
    """返回配置化的文本切分器。"""
    return TextSplitter(
        chunk_size=getattr(settings, "music_knowledge_chunk_size", _DEFAULT_CHUNK_SIZE),
        chunk_overlap=getattr(settings, "music_knowledge_chunk_overlap", _DEFAULT_CHUNK_OVERLAP),
    )


def _get_vector_store() -> VectorStore:
    """返回默认的向量存储实例。"""
    return VectorStore(embedding_client=EmbeddingClient())


async def ingest_document(
    db: AsyncSession,
    filename: str,
    file: BinaryIO,
) -> IngestResult:
    """解析文档、切分、嵌入并写入音乐知识向量库。

    同名文档会幂等覆盖：先删除该 source 的旧片段，再写入新片段。

    参数:
        db: 异步数据库会话。
        filename: 原始文件名，用于识别文件类型与作为 source 标识。
        file: 二进制文件对象。

    返回:
        IngestResult，包含 source 与 chunk_count。

    异常:
        ValueError: 文件类型不支持或解析失败时抛出。
    """
    source = _normalize_source(filename)
    file_type = _file_extension(filename)

    text = parse_document(file, filename)
    splitter = _get_splitter()
    chunks = splitter.split(text)

    # 幂等：先删除旧数据
    await delete_by_source(db, source)

    if not chunks:
        logger.info("No text chunks generated for music knowledge document: %s", source)
        return IngestResult(source=source, chunk_count=0)

    vector_store = _get_vector_store()
    metas = _build_metas(source, file_type, len(chunks))
    await vector_store.add_batch(
        db,
        namespace=MUSIC_KNOWLEDGE_NAMESPACE,
        contents=chunks,
        metas=metas,
    )
    await db.commit()

    logger.info(
        "Ingested music knowledge document: %s, chunks=%d",
        source,
        len(chunks),
    )
    return IngestResult(source=source, chunk_count=len(chunks))


async def list_sources(
    db: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[str], int]:
    """按 source 去重列出已入库文档名。

    参数:
        db: 异步数据库会话。
        limit: 返回数量上限。
        offset: 偏移量。

    返回:
        (source 列表, 总数)。
    """
    subq = (
        select(VectorDocument.meta["source"].astext.label("source"))
        .where(VectorDocument.namespace == MUSIC_KNOWLEDGE_NAMESPACE)
        .where(VectorDocument.meta["source"].astext.isnot(None))
        .distinct()
        .subquery()
    )
    total = (await db.execute(select(func.count()).select_from(subq))).scalar_one()

    stmt = (
        select(subq.c.source)
        .order_by(subq.c.source)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = [row[0] for row in result.all() if row[0]]
    return items, total


async def delete_by_source(db: AsyncSession, source: str) -> int:
    """删除指定 source 的全部向量片段。

    参数:
        db: 异步数据库会话。
        source: 文档 source 标识（文件名）。

    返回:
        删除的记录数。
    """
    stmt = (
        delete(VectorDocument)
        .where(VectorDocument.namespace == MUSIC_KNOWLEDGE_NAMESPACE)
        .where(VectorDocument.meta["source"].astext == source)
    )
    result = await db.execute(stmt)
    count = result.rowcount
    if count:
        logger.info(
            "Deleted %d chunks for music knowledge document: %s",
            count,
            source,
        )
    return count
