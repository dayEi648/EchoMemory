"""AI 对话会话相关的 ORM 模型定义。

真正的消息内容通过 LangGraph Checkpointer 持久化到 PostgreSQL，
本模型仅保存会话级元数据。
"""

from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class AIConversationStatus(IntEnum):
    """AI 会话状态枚举。"""

    ACTIVE = 0
    ARCHIVED = 1
    DELETED = 2


class AIConversation(Base):
    """AI 对话会话元数据模型。

    消息历史由 LangGraph 的 AsyncPostgresSaver 管理，
    ``thread_id`` 用于定位 checkpoint 中的状态。
    """

    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[int] = mapped_column(
        SmallInteger, default=AIConversationStatus.ACTIVE, nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_evaluated_human_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "profile_evaluated_human_count >= 0",
            name="chk_ai_conversations_profile_evaluated_count",
        ),
        Index(
            "idx_ai_conversations_user_status_time",
            "user_id",
            "status",
            "updated_at",
        ),
        Index("idx_ai_conversations_thread_id", "thread_id", unique=True),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
