"""音乐知识库管理 API Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MusicKnowledgeDocumentOut(BaseModel):
    """单个已入库文档信息。"""

    source: str
    chunk_count: int


class MusicKnowledgeIngestOut(BaseModel):
    """文档入库响应。"""

    source: str
    chunk_count: int


class MusicKnowledgeSourceListOut(BaseModel):
    """已入库文档列表响应。"""

    items: list[str]
    total: int


class MusicKnowledgeDeleteOut(BaseModel):
    """删除文档响应。"""

    deleted_chunks: int


class MusicKnowledgeSourceParams(BaseModel):
    """文档列表查询参数。"""

    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
