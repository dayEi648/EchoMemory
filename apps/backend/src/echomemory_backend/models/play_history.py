from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.user import User


class PlayHistory(Base):
    __tablename__ = "play_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), nullable=False
    )
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_play_history_user_time", "user_id", desc("played_at")),
    )

    user: Mapped["User"] = relationship("User", back_populates="play_history")
    music: Mapped["Music"] = relationship("Music")
