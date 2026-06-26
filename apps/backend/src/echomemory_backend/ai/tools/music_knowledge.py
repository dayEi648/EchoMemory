"""音乐知识库检索工具。

供 AI 对话 Agent 主动查询已入库的音乐知识片段。
"""

from __future__ import annotations

from typing import Annotated

from langchain.tools import tool
from pydantic import Field

from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.rag.embeddings import EmbeddingClient
from echomemory_backend.rag.vector_store import VectorStore
from echomemory_backend.services.music_knowledge_service import (
    MUSIC_KNOWLEDGE_NAMESPACE,
)


@tool
async def search_music_knowledge(
    query: str,
    top_k: Annotated[int, Field(ge=1, le=10)] = 5,
) -> dict[str, object]:
    """检索音乐知识库中与 query 相关的文本片段。

    当用户询问音乐知识、艺人背景、乐理概念、曲风解释、平台规则、创作技巧等
    事实性问题，且音乐平台目录工具无法直接回答时使用。

    Args:
        query: 检索用的问题或关键词，应保留用户原始意图中的关键概念。
        top_k: 返回结果数量上限，范围 1 到 10。

    Returns:
        包含 ``items`` 与 ``total`` 的字典。``items`` 为知识片段列表，每项含
        ``content``（片段文本）、``source``（来源文档名）、
        ``chunk_index``（片段序号）、``total_chunks``（文档总片段数）。
        返回的 source 与 chunk_index 仅用于内部定位，不要在自然语言回复中展示。
    """
    async with AsyncSessionLocal() as db:
        vector_store = VectorStore(embedding_client=EmbeddingClient())
        docs = await vector_store.search(
            db,
            namespace=MUSIC_KNOWLEDGE_NAMESPACE,
            query=query,
            top_k=top_k,
        )

    items = [
        {
            "content": doc.content,
            "source": doc.meta.get("source") if doc.meta else None,
            "chunk_index": doc.meta.get("chunk_index") if doc.meta else None,
            "total_chunks": doc.meta.get("total_chunks") if doc.meta else None,
        }
        for doc in docs
    ]
    return {"items": items, "total": len(items)}
