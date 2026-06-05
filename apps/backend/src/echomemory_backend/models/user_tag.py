from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base


class UserEmotionTag(Base):
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
