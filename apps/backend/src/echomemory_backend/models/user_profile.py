"""用户画像数据模型。

每个用户维护一条画像记录，用于在 AI 对话中提供长期记忆与个性化上下文。
画像内容为自然语言文本，长度限制 500 字，初始为空。
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class UserProfile(Base):
    """用户画像模型。

    画像内容不超过 500 个字符，由 AI 根据用户对话历史自动维护。
    """

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_user_profiles_updated_at", "updated_at"),
    )

    user: Mapped["User"] = relationship("User", back_populates="profile")
