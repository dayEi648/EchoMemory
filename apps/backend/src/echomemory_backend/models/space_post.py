from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    SmallInteger,
    String,
    Text,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class SpacePost(Base):
    __tablename__ = "space_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text)
    post_type: Mapped[str] = mapped_column(String(20), default="original", nullable=False)
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    source_type: Mapped[str | None] = mapped_column(String(20))
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    forward_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "post_type IN ('original', 'forward')", name="chk_space_posts_post_type"
        ),
        CheckConstraint(
            "(post_type = 'original' AND source_id IS NULL AND source_type IS NULL) OR "
            "(post_type = 'forward' AND source_id IS NOT NULL AND source_type IS NOT NULL)",
            name="chk_space_posts_source_consistency",
        ),
        Index(
            "idx_space_posts_user_time",
            "user_id",
            desc("created_at"),
            postgresql_where=is_deleted.is_(False) & is_private.is_(False),
        ),
        Index(
            "idx_space_posts_created_at",
            desc("created_at"),
            postgresql_where=is_deleted.is_(False) & is_private.is_(False),
        ),
    )

    user: Mapped["User"] = relationship("User", back_populates="space_posts")
    images: Mapped[list["SpacePostImage"]] = relationship(
        "SpacePostImage", back_populates="post"
    )
    likes: Mapped[list["SpacePostLike"]] = relationship(
        "SpacePostLike", back_populates="post"
    )


class SpacePostImage(Base):
    __tablename__ = "space_post_images"

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("space_posts.id", ondelete="CASCADE"), primary_key=True
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    ordinal: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "ordinal >= 0", name="chk_space_post_images_ordinal_nonnegative"
        ),
    )

    post: Mapped["SpacePost"] = relationship("SpacePost", back_populates="images")


class SpacePostLike(Base):
    __tablename__ = "space_post_likes"

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("space_posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_space_post_likes_user", "user_id"),)

    post: Mapped["SpacePost"] = relationship("SpacePost", back_populates="likes")
    user: Mapped["User"] = relationship("User")
