"""VectorStore 基础设施测试。

使用内存中 Fake Embedding Client 与测试数据库，验证向量增删查逻辑。
"""

import hashlib

import pytest

from echomemory_backend.models.vector_document import VectorDocument
from echomemory_backend.rag.embeddings import EmbeddingClient
from echomemory_backend.rag.vector_store import VectorStore


class _FakeEmbeddingClient:
    """确定性假嵌入客户端，避免调用外部 API。"""

    def __init__(self, dimensions: int = 1024) -> None:
        self.dimensions = dimensions
        self.model = "fake-embedding"

    def _vector_for(self, text: str) -> list[float]:
        digest = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        index = digest % self.dimensions
        vector = [0.0] * self.dimensions
        vector[index] = 1.0
        return vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(t) for t in texts]

    async def embed_one(self, text: str) -> list[float]:
        return self._vector_for(text)


@pytest.fixture
def vector_store():
    return VectorStore(embedding_client=_FakeEmbeddingClient())


async def test_add_and_search(vector_store, db_session):
    """写入文档后应能按语义检索到。"""
    doc = await vector_store.add(
        db_session,
        namespace="music_knowledge",
        content="周杰伦的晴天是一首经典华语流行歌曲",
        meta={"source": "test"},
    )

    assert doc.id is not None
    assert doc.namespace == "music_knowledge"
    assert doc.content == "周杰伦的晴天是一首经典华语流行歌曲"
    assert doc.meta == {"source": "test"}
    assert len(doc.embedding) == 1024

    results = await vector_store.search(
        db_session,
        namespace="music_knowledge",
        query="周杰伦 晴天 歌曲",
        top_k=3,
    )

    assert len(results) == 1
    assert results[0].id == doc.id


async def test_search_isolated_by_namespace(vector_store, db_session):
    """不同命名空间的数据应互不干扰。"""
    await vector_store.add(db_session, namespace="A", content="内容 A")
    await vector_store.add(db_session, namespace="B", content="内容 B")

    results = await vector_store.search(db_session, namespace="A", query="内容")
    assert len(results) == 1
    assert results[0].namespace == "A"


async def test_search_respects_top_k(vector_store, db_session):
    """search 应受 top_k 限制。"""
    await vector_store.add(db_session, namespace="topk_test", content="苹果")
    await vector_store.add(db_session, namespace="topk_test", content="香蕉")
    await vector_store.add(db_session, namespace="topk_test", content="橙子")

    results = await vector_store.search(db_session, namespace="topk_test", query="水果", top_k=2)
    assert len(results) == 2


async def test_search_invalid_top_k(vector_store, db_session):
    """top_k 小于等于 0 应触发 ValueError。"""
    with pytest.raises(ValueError):
        await vector_store.search(db_session, namespace="x", query="y", top_k=0)


async def test_add_batch(vector_store, db_session):
    """批量写入应返回与输入顺序一致的文档。"""
    docs = await vector_store.add_batch(
        db_session,
        namespace="batch_test",
        contents=["第一条", "第二条", "第三条"],
        metas=[{"i": 1}, {"i": 2}, {"i": 3}],
    )

    assert len(docs) == 3
    assert [d.content for d in docs] == ["第一条", "第二条", "第三条"]


async def test_add_batch_empty_returns_empty(vector_store, db_session):
    """空 contents 应返回空列表。"""
    docs = await vector_store.add_batch(db_session, namespace="empty", contents=[])
    assert docs == []


async def test_add_batch_rejects_mismatched_metas(vector_store, db_session):
    """metas 长度与 contents 不一致应触发 ValueError。"""
    with pytest.raises(ValueError):
        await vector_store.add_batch(
            db_session,
            namespace="mismatch",
            contents=["a", "b"],
            metas=[{"i": 1}],
        )


async def test_get_by_id(vector_store, db_session):
    """get_by_id 应能根据 ID 读取文档。"""
    doc = await vector_store.add(db_session, namespace="get_test", content="测试内容")
    fetched = await vector_store.get_by_id(db_session, doc.id)

    assert fetched is not None
    assert fetched.id == doc.id
    assert fetched.content == "测试内容"

    missing = await vector_store.get_by_id(db_session, -1)
    assert missing is None


async def test_delete_by_id(vector_store, db_session):
    """根据 ID 删除后文档应消失。"""
    doc = await vector_store.add(db_session, namespace="delete_test", content="待删除")
    deleted = await vector_store.delete_by_id(db_session, doc.id)
    assert deleted is True

    results = await vector_store.search(db_session, namespace="delete_test", query="待删除")
    assert len(results) == 0


async def test_delete_by_namespace(vector_store, db_session):
    """按命名空间删除应清空该空间全部文档。"""
    await vector_store.add(db_session, namespace="clear_me", content="文档一")
    await vector_store.add(db_session, namespace="clear_me", content="文档二")

    count = await vector_store.delete_by_namespace(db_session, "clear_me")
    assert count == 2

    results = await vector_store.search(db_session, namespace="clear_me", query="文档")
    assert len(results) == 0
