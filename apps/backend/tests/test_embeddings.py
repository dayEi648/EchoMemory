"""Embedding 客户端基础设施测试。

本模块仅验证配置加载、客户端构造与请求封装逻辑，不调用真实 DashScope API。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from echomemory_backend.core.config import settings
from echomemory_backend.rag.embeddings import EmbeddingClient


def test_settings_loads_embedding_defaults():
    """配置应加载 Embedding 默认值。"""
    assert settings.embedding_base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert settings.embedding_model == "text-embedding-v4"
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_batch_size == 25


def test_embedding_client_uses_defaults():
    """客户端未传参时应使用配置默认值。"""
    client = EmbeddingClient()
    assert client.model == "text-embedding-v4"
    assert client.dimensions == 1024
    assert client.batch_size == 25


def test_embedding_client_requires_model():
    """空模型应触发 ValueError。"""
    with pytest.raises(ValueError):
        EmbeddingClient(model="")


def test_embedding_client_requires_positive_dimensions():
    """非正维度应触发 ValueError。"""
    with pytest.raises(ValueError):
        EmbeddingClient(dimensions=0)


def test_embedding_client_requires_positive_batch_size():
    """非正批次大小应触发 ValueError。"""
    with pytest.raises(ValueError):
        EmbeddingClient(batch_size=0)


async def test_embed_returns_vectors():
    """批量嵌入应返回与输入顺序一致的向量列表。"""
    client = EmbeddingClient(api_key="test-key")
    vec1 = [0.1] * client.dimensions
    vec2 = [0.4] * client.dimensions

    item1 = MagicMock()
    item1.embedding = vec1
    item2 = MagicMock()
    item2.embedding = vec2
    response = MagicMock()
    response.data = [item1, item2]

    with patch.object(
        client._client.embeddings, "create", new=AsyncMock(return_value=response)
    ):
        result = await client.embed(["hello", "world"])

    assert result == [vec1, vec2]


async def test_embed_one_returns_single_vector():
    """单条嵌入应返回单个向量。"""
    client = EmbeddingClient(api_key="test-key")
    vec = [0.1] * client.dimensions

    item = MagicMock()
    item.embedding = vec
    response = MagicMock()
    response.data = [item]

    with patch.object(
        client._client.embeddings, "create", new=AsyncMock(return_value=response)
    ):
        result = await client.embed_one("hello")

    assert result == vec


async def test_embed_rejects_empty_list():
    """空列表应触发 ValueError。"""
    client = EmbeddingClient(api_key="test-key")
    with pytest.raises(ValueError):
        await client.embed([])


async def test_embed_batches_requests_by_batch_size():
    """输入超过 batch_size 时应分多次调用 API。"""
    client = EmbeddingClient(api_key="test-key", dimensions=4, batch_size=2)

    call_count = 0
    async def _fake_create(*, input, **kwargs):
        nonlocal call_count
        start_index = call_count * client.batch_size
        call_count += 1
        response = MagicMock()
        response.data = [
            MagicMock(embedding=[float(start_index + i)] * client.dimensions)
            for i in range(len(input))
        ]
        return response

    with patch.object(client._client.embeddings, "create", new=_fake_create):
        result = await client.embed(["a", "b", "c", "d"])

    assert call_count == 2
    assert len(result) == 4
    assert result[0] == [0.0] * client.dimensions
    assert result[3] == [3.0] * client.dimensions


def test_embedding_client_accepts_custom_params():
    """客户端应支持传入自定义参数覆盖默认值。"""
    client = EmbeddingClient(
        model="custom-model",
        api_key="test-key",
        base_url="https://custom.example.com/v1",
        dimensions=512,
        batch_size=10,
    )
    assert client.model == "custom-model"
    assert client.dimensions == 512
    assert client.batch_size == 10
