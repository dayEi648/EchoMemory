"""内容申诉模型 — 用户对审核结果发起申诉的记录。"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from echomemory_backend.db.base import Base


class ContentAppeal(Base):
    """用户对审核决定发起的申诉。"""

    __tablename__ = "content_appeals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    moderation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PENDING", server_default="PENDING"
    )
    appeal_reason: Mapped[str | None] = mapped_column(Text)
    admin_note: Mapped[str | None] = mapped_column(Text)
    reviewer_user_id: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "content_type IN ('comment', 'space_post', 'playlist', 'user_profile')",
            name="chk_content_appeals_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'DENIED')",
            name="chk_content_appeals_status",
        ),
        # 同一内容同一审核版本最多一个待处理申诉（通过部分唯一索引实现）
        Index(
            "uq_content_appeal_pending",
            "content_type",
            "content_id",
            "moderation_version",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("idx_content_appeals_status", "status", "created_at"),
        Index("idx_content_appeals_user", "user_id", "created_at"),
    )
