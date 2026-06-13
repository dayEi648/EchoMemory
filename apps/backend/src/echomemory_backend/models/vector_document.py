"""定义向量文档模型，用于 RAG 知识库存储与检索。"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from echomemory_backend.core.config import settings
from echomemory_backend.db.base import Base


class VectorDocument(Base):
    """RAG 向量文档表。

    存储文本片段、原始内容、业务元数据与 embedding 向量，
    按 ``namespace`` 隔离不同知识库或用户空间。
    """

    __tablename__ = "vector_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    namespace: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_vector_documents_namespace_created", "namespace", "created_at"),
    )
