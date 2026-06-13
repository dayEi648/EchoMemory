"""用户推荐相关的数据库模型，记录每日推荐与私人雷达的每日结果。"""

from datetime import date as date_type
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class UserDailyRecommendation(Base):
    """用户每日推荐结果表。

    每天为每个用户生成一次，保存当天推荐的最多 10 首音乐 ID。
    """

    __tablename__ = "user_daily_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    music_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False, default=list
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
        UniqueConstraint("user_id", "date", name="uq_user_daily_recommendations"),
        Index("idx_user_daily_recommendations_date", "date"),
        Index("idx_user_daily_recommendations_user_date", "user_id", "date"),
    )

    user: Mapped["User"] = relationship("User")


class UserRadarRecommendation(Base):
    """用户私人雷达结果表。

    每天为每个用户生成一次，保存当天私人雷达的最多 20 首音乐 ID。
    """

    __tablename__ = "user_radar_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    music_ids: Mapped[list[int]] = mapped_column(
        ARRAY(BigInteger), nullable=False, default=list
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
        UniqueConstraint("user_id", "date", name="uq_user_radar_recommendations"),
        Index("idx_user_radar_recommendations_date", "date"),
        Index("idx_user_radar_recommendations_user_date", "user_id", "date"),
    )

    user: Mapped["User"] = relationship("User")
