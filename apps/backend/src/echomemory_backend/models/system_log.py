"""定义系统日志数据库模型，用于持久化后端 WARNING 及以上级别日志。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from echomemory_backend.db.base import Base


class SystemLog(Base):
    """系统日志模型。

    记录后端产生的 WARNING、ERROR、CRITICAL 级别日志，以及关联的
    请求上下文（方法、路径、请求体、响应体）和堆栈信息。
    """

    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    logger: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    request_method: Mapped[str | None] = mapped_column(String(10))
    request_path: Mapped[str | None] = mapped_column(String(500))
    request_body: Mapped[str | None] = mapped_column(Text)
    response_body: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_system_logs_level_created", "level", "created_at"),
        Index("idx_system_logs_created_at", "created_at"),
        Index(
            "idx_system_logs_message_gin",
            "message",
            postgresql_using="gin",
            postgresql_ops={"message": "gin_trgm_ops"},
        ),
    )
