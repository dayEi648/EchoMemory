"""空间动态（SpacePost）相关的 ORM 模型定义模块。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    """用户空间动态帖子模型。"""

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
    safety: Mapped[int] = mapped_column(SmallInteger, default=10, nullable=False)
    recommendation_score: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False
    )
    safety_level: Mapped[str | None] = mapped_column(String(16))
    recommendation_level: Mapped[str | None] = mapped_column(String(16))
    moderation_status: Mapped[str] = mapped_column(
        String(16), default="PENDING", nullable=False
    )
    moderation_reason: Mapped[str | None] = mapped_column(Text)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    deletion_reason: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (
        CheckConstraint(
            "post_type IN ('original', 'forward')", name="chk_space_posts_post_type"
        ),
        CheckConstraint(
            "safety BETWEEN 0 AND 10", name="chk_space_posts_safety"
        ),
        CheckConstraint(
            "recommendation_score BETWEEN 0 AND 10",
            name="chk_space_posts_recommendation_score",
        ),
        CheckConstraint(
            "safety_level IS NULL OR safety_level IN ('SAFE', 'RISKY', 'DANGEROUS')",
            name="chk_space_posts_safety_level",
        ),
        CheckConstraint(
            "recommendation_level IS NULL OR recommendation_level IN ('NORMAL', 'RECOMMENDED')",
            name="chk_space_posts_recommendation_level",
        ),
        CheckConstraint(
            "moderation_status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'MANUAL')",
            name="chk_space_posts_moderation_status",
        ),
        CheckConstraint(
            "moderation_version > 0", name="chk_space_posts_moderation_version"
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
        Index(
            "idx_space_posts_moderation_admin",
            "moderation_status",
            "is_deleted",
            desc("created_at"),
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
    """空间动态关联的图片模型。"""

    __tablename__ = "space_post_images"

    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("space_posts.id", ondelete="CASCADE"), primary_key=True
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    ordinal: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False, primary_key=True
    )
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
    """空间动态点赞记录模型。"""

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
