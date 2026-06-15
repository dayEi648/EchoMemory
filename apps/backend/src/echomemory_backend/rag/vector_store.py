"""基于 PostgreSQL pgvector 的向量存储封装。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.vector_document import VectorDocument
from echomemory_backend.rag.embeddings import EmbeddingClient


__all__ = ["VectorStore"]


class VectorStore:
    """向量存储仓库，负责文档嵌入、持久化与语义检索。

    所有数据按 ``namespace`` 隔离，可用于区分不同知识库或用户空间。

    注意：本类所有方法均不会主动提交 ``session``，由调用方控制事务边界。
    """

    def __init__(self, embedding_client: EmbeddingClient) -> None:
        """初始化向量存储。

        参数:
            embedding_client: 用于生成文本向量的嵌入客户端。
        """
        self._embedding_client = embedding_client

    def _validate_embedding(self, embedding: list[float]) -> list[float]:
        """校验向量维度与内容。

        参数:
            embedding: 待校验的向量。

        返回:
            校验通过的向量。

        异常:
            ValueError: 向量为空或维度与配置不一致时抛出。
        """
        expected = self._embedding_client.dimensions
        if not embedding:
            raise ValueError("embedding 不能为空")
        if len(embedding) != expected:
            raise ValueError(
                f"embedding 维度应为 {expected}，实际为 {len(embedding)}"
            )
        return embedding

    async def add(
        self,
        session: AsyncSession,
        namespace: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> VectorDocument:
        """将单条文本写入向量库。

        参数:
            session: 异步数据库会话。
            namespace: 命名空间，用于隔离不同知识库。
            content: 原始文本内容。
            meta: 业务元数据，例如来源 ID、类型等。

        返回:
            保存后的 VectorDocument 对象。

        注意:
            本方法不会提交 session，调用方需自行调用 ``await session.commit()``。
        """
        embedding = self._validate_embedding(
            await self._embedding_client.embed_one(content)
        )
        doc = VectorDocument(
            namespace=namespace,
            content=content,
            meta=meta,
            embedding=embedding,
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)
        return doc

    async def add_batch(
        self,
        session: AsyncSession,
        namespace: str,
        contents: list[str],
        metas: list[dict[str, Any] | None] | None = None,
    ) -> list[VectorDocument]:
        """将多条文本批量写入向量库。

        参数:
            session: 异步数据库会话。
            namespace: 命名空间。
            contents: 原始文本内容列表。
            metas: 与 contents 一一对应的元数据列表；None 表示全部为空。

        返回:
            保存后的 VectorDocument 对象列表。

        异常:
            ValueError: contents 为空列表，或 metas 长度与 contents 不一致时抛出。

        注意:
            本方法不会提交 session，调用方需自行调用 ``await session.commit()``。
        """
        if not contents:
            return []

        metas = metas or [None] * len(contents)
        if len(contents) != len(metas):
            raise ValueError("contents 与 metas 长度必须一致")

        embeddings = await self._embedding_client.embed(contents)

        docs: list[VectorDocument] = []
        for content, embedding, meta in zip(contents, embeddings, metas, strict=True):
            doc = VectorDocument(
                namespace=namespace,
                content=content,
                meta=meta,
                embedding=self._validate_embedding(embedding),
            )
            session.add(doc)
            docs.append(doc)

        await session.flush()
        for doc in docs:
            await session.refresh(doc)
        return docs

    async def search(
        self,
        session: AsyncSession,
        namespace: str,
        query: str,
        top_k: int = 5,
    ) -> list[VectorDocument]:
        """在指定命名空间内进行语义检索。

        使用余弦距离（``<=>``）排序，返回距离最近的 ``top_k`` 条记录。

        参数:
            session: 异步数据库会话。
            namespace: 命名空间。
            query: 查询文本。
            top_k: 返回结果数量上限，必须大于 0。

        返回:
            按相似度排序的 VectorDocument 列表。

        异常:
            ValueError: top_k 小于等于 0 时抛出。
        """
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")

        query_embedding = self._validate_embedding(
            await self._embedding_client.embed_one(query)
        )
        stmt = (
            select(VectorDocument)
            .where(VectorDocument.namespace == namespace)
            .order_by(VectorDocument.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(
        self,
        session: AsyncSession,
        doc_id: int,
    ) -> VectorDocument | None:
        """根据 ID 获取单条向量文档。

        参数:
            session: 异步数据库会话。
            doc_id: 文档 ID。

        返回:
            VectorDocument 对象；不存在时返回 None。
        """
        stmt = select(VectorDocument).where(VectorDocument.id == doc_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_by_namespace(
        self,
        session: AsyncSession,
        namespace: str,
    ) -> int:
        """删除指定命名空间下的全部向量文档。

        参数:
            session: 异步数据库会话。
            namespace: 命名空间。

        返回:
            删除的记录数。

        注意:
            本方法不会提交 session，调用方需自行调用 ``await session.commit()``。
        """
        stmt = delete(VectorDocument).where(VectorDocument.namespace == namespace)
        result = await session.execute(stmt)
        return result.rowcount

    async def delete_by_id(
        self,
        session: AsyncSession,
        doc_id: int,
    ) -> bool:
        """根据 ID 删除单条向量文档。

        参数:
            session: 异步数据库会话。
            doc_id: 文档 ID。

        返回:
            是否成功删除。

        注意:
            本方法不会提交 session，调用方需自行调用 ``await session.commit()``。
        """
        stmt = delete(VectorDocument).where(VectorDocument.id == doc_id)
        result = await session.execute(stmt)
        return result.rowcount > 0
