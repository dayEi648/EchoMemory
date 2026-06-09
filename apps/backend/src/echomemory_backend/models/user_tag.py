"""用户与标签的关联模型模块，定义用户情绪标签和用户兴趣标签的多对多关联表。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.dictionary import EmotionTag, InterestTag
    from echomemory_backend.models.user import User


class UserEmotionTag(Base):
    """用户与情绪标签的关联表模型。"""

    __tablename__ = "user_emotion_tags"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    emotion_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("emotion_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_user_emotion_tags_tag_id", "emotion_tag_id"),)

    user: Mapped["User"] = relationship("User")
    emotion_tag: Mapped["EmotionTag"] = relationship("EmotionTag")


class UserInterestTag(Base):
    """用户与兴趣标签的关联表模型。"""

    __tablename__ = "user_interest_tags"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    interest_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interest_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_user_interest_tags_tag_id", "interest_tag_id"),)

    user: Mapped["User"] = relationship("User")
    interest_tag: Mapped["InterestTag"] = relationship("InterestTag")
