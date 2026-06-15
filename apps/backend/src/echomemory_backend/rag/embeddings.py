"""阿里云 DashScope text-embedding-v4 嵌入模型封装。

基于 OpenAI 兼容接口访问 DashScope，提供文本到向量的异步转换能力。
"""

from __future__ import annotations

from openai import AsyncOpenAI

from echomemory_backend.core.config import get_settings


__all__ = ["EmbeddingClient"]


class EmbeddingClient:
    """text-embedding-v4 专属异步客户端。

    使用 OpenAI 兼容协议访问阿里云 DashScope，支持单条与批量嵌入。
    批量请求会自动按 ``embedding_batch_size`` 切分，避免超过服务端限制。
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
        timeout: float = 60.0,
    ) -> None:
        """初始化 Embedding 客户端。

        参数:
            model: 使用的模型 ID，默认 ``settings.embedding_model``。
            api_key: DashScope API 密钥，默认 ``settings.dashscope_api_key``。
            base_url: OpenAI 兼容端点，默认 ``settings.embedding_base_url``。
            dimensions: 输出向量维度，默认 ``settings.embedding_dimensions``。
            batch_size: 单次批量最大条数，默认 ``settings.embedding_batch_size``。
            timeout: 单次请求超时时间（秒）。

        异常:
            ValueError: 当 model 为空或 dimensions 非正数时抛出。
        """
        settings = get_settings()
        model = model if model is not None else settings.embedding_model
        if not model:
            raise ValueError("model 不能为空")

        dimensions = dimensions if dimensions is not None else settings.embedding_dimensions
        if dimensions <= 0:
            raise ValueError("dimensions 必须大于 0")

        self.model = model
        self.dimensions = dimensions
        batch_size = batch_size if batch_size is not None else settings.embedding_batch_size
        self.batch_size = batch_size
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")

        self._client = AsyncOpenAI(
            api_key=api_key if api_key is not None else settings.dashscope_api_key,
            base_url=base_url if base_url is not None else settings.embedding_base_url,
            timeout=timeout,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表转换为向量列表。

        参数:
            texts: 待嵌入的文本列表。

        返回:
            与输入顺序一致的向量列表，每个向量的长度等于 ``dimensions``。

        异常:
            ValueError: 当 texts 为空列表时抛出。
            openai.APIError: DashScope API 返回错误时抛出。
        """
        if not texts:
            raise ValueError("texts 不能为空列表")

        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = await self._client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
                encoding_format="float",
            )
            if len(response.data) != len(batch):
                raise ValueError(
                    f"embedding 响应数量不匹配：期望 {len(batch)}，实际 {len(response.data)}"
                )
            for item in response.data:
                embedding = item.embedding
                if not embedding:
                    raise ValueError("embedding 响应包含空向量")
                if len(embedding) != self.dimensions:
                    raise ValueError(
                        f"embedding 维度应为 {self.dimensions}，实际为 {len(embedding)}"
                    )
                results.append(embedding)
        return results

    async def embed_one(self, text: str) -> list[float]:
        """将单条文本转换为向量。

        参数:
            text: 待嵌入的文本。

        返回:
            长度为 ``dimensions`` 的向量。

        异常:
            openai.APIError: DashScope API 返回错误时抛出。
        """
        embeddings = await self.embed([text])
        return embeddings[0]
