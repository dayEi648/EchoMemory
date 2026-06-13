"""播放历史记录的数据库模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.user import User


class PlayHistory(Base):
    """用户音乐播放历史记录模型，记录用户播放音乐的日志。"""
    __tablename__ = "play_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), nullable=False
    )
    play_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("play_count >= 1", name="chk_play_history_play_count_positive"),
        Index("uq_play_history_user_music", "user_id", "music_id", unique=True),
        Index("idx_play_history_user_time", "user_id", desc("played_at")),
        Index("idx_play_history_music_time", "music_id", desc("played_at")),
    )

    user: Mapped["User"] = relationship("User", back_populates="play_history")
    music: Mapped["Music"] = relationship("Music")
