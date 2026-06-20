"""定义用户相关的数据库模型，包括用户基本信息与关注关系。"""

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Interval,
    SmallInteger,
    String,
    Text,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.comment import Comment
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.play_history import PlayHistory
    from echomemory_backend.models.playlist import Playlist
    from echomemory_backend.models.space_post import SpacePost
    from echomemory_backend.models.user_profile import UserProfile


class User(Base):
    """用户数据模型，存储平台用户的基本信息、状态及关联关系。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(32), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    role: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    safety_score: Mapped[int] = mapped_column(SmallInteger, default=10, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    city: Mapped[str | None] = mapped_column(String(50))
    birth: Mapped[date | None] = mapped_column(Date)
    bio: Mapped[str | None] = mapped_column(Text)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ban_duration: Mapped[timedelta | None] = mapped_column(Interval)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("gender >= 0 AND gender <= 2", name="chk_users_gender"),
        CheckConstraint("role >= 0 AND role <= 3", name="chk_users_role"),
        CheckConstraint("status >= 0 AND status <= 3", name="chk_users_status"),
        CheckConstraint(
            "safety_score >= 0 AND safety_score <= 10", name="chk_users_safety_score"
        ),
        CheckConstraint("exp >= 0", name="chk_users_exp_nonnegative"),
        CheckConstraint("level >= 0", name="chk_users_level_nonnegative"),
        CheckConstraint("like_count >= 0", name="chk_users_like_count_nonnegative"),
        CheckConstraint(
            "(banned_at IS NULL AND status NOT IN (1, 2, 3)) OR (banned_at IS NOT NULL AND status IN (1, 2, 3))",
            name="chk_users_ban_consistency",
        ),
        CheckConstraint(
            "ban_duration IS NULL OR ban_duration > INTERVAL '0'",
            name="chk_users_ban_duration_positive",
        ),
        CheckConstraint(
            "ban_duration IS NULL OR banned_at IS NOT NULL",
            name="chk_users_ban_dates",
        ),
        Index(
            "idx_users_email", "email", unique=True, postgresql_where=email.is_not(None)
        ),
        Index(
            "idx_users_phone", "phone", unique=True, postgresql_where=phone.is_not(None)
        ),
        Index("idx_users_exp", desc("exp")),
        Index("idx_users_created_at", desc("created_at")),
        Index("idx_users_status", "status", postgresql_where=is_deleted.is_(False)),
        Index("idx_users_level", "level"),
        Index("idx_users_last_login_at", desc("last_login_at")),
        Index(
            "idx_users_banned_at", "banned_at", postgresql_where=banned_at.is_not(None)
        ),
        Index(
            "idx_users_nickname_trgm",
            "nickname",
            postgresql_using="gin",
            postgresql_ops={"nickname": "gin_trgm_ops"},
        ),
        Index(
            "idx_users_username_trgm",
            "username",
            postgresql_using="gin",
            postgresql_ops={"username": "gin_trgm_ops"},
        ),
    )

    playlists: Mapped[list["Playlist"]] = relationship("Playlist", back_populates="user")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="user")
    space_posts: Mapped[list["SpacePost"]] = relationship(
        "SpacePost", back_populates="user"
    )
    play_history: Mapped[list["PlayHistory"]] = relationship(
        "PlayHistory", back_populates="user"
    )
    following: Mapped[list["UserFollow"]] = relationship(
        "UserFollow", foreign_keys="UserFollow.follower_id", back_populates="follower"
    )
    followers: Mapped[list["UserFollow"]] = relationship(
        "UserFollow", foreign_keys="UserFollow.followee_id", back_populates="followee"
    )
    profile: Mapped["UserProfile | None"] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )


class UserFollow(Base):
    """用户关注关系数据模型，记录用户之间的关注行为。"""

    __tablename__ = "user_follows"

    follower_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    followee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "follower_id <> followee_id", name="chk_user_follows_no_self_follow"
        ),
        Index("idx_user_follows_followee", "followee_id"),
        Index("idx_user_follows_follower_time", "follower_id", desc("created_at")),
        Index("idx_user_follows_followee_time", "followee_id", desc("created_at")),
    )

    follower: Mapped["User"] = relationship(
        "User", foreign_keys=[follower_id], back_populates="following"
    )
    followee: Mapped["User"] = relationship(
        "User", foreign_keys=[followee_id], back_populates="followers"
    )
