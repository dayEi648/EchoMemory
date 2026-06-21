"""评论相关的数据库模型，包含评论主体、点赞和点踩记录。"""

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
    SmallInteger,
    Text,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.user import User


class Comment(Base):
    """评论模型，用于存储用户对音乐、歌单或空间动态的评论内容。"""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    music_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE")
    )
    playlist_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("playlists.id", ondelete="CASCADE")
    )
    space_post_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("space_posts.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE")
    )
    root_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE")
    )
    is_nested_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    safety: Mapped[int] = mapped_column(SmallInteger, default=10, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    dislike_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint("safety >= 0 AND safety <= 10", name="chk_comments_safety"),
        CheckConstraint(
            "(music_id IS NOT NULL)::int + (playlist_id IS NOT NULL)::int + (space_post_id IS NOT NULL)::int = 1",
            name="chk_comment_target_unique",
        ),
        Index(
            "idx_comments_music_root",
            "music_id",
            desc("created_at"),
            postgresql_where=parent_id.is_(None) & is_deleted.is_(False),
        ),
        Index(
            "idx_comments_playlist_root",
            "playlist_id",
            desc("created_at"),
            postgresql_where=parent_id.is_(None) & is_deleted.is_(False),
        ),
        Index(
            "idx_comments_space_root",
            "space_post_id",
            desc("created_at"),
            postgresql_where=parent_id.is_(None) & is_deleted.is_(False),
        ),
        Index("idx_comments_root_time", "root_id", desc("created_at")),
        Index("idx_comments_user_id", "user_id"),
    )

    user: Mapped["User"] = relationship("User", back_populates="comments")
    likes: Mapped[list["CommentLike"]] = relationship("CommentLike", back_populates="comment")
    dislikes: Mapped[list["CommentDislike"]] = relationship(
        "CommentDislike", back_populates="comment"
    )


class CommentLike(Base):
    """评论点赞模型，记录用户对评论的点赞关系。"""

    __tablename__ = "comment_likes"

    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_comment_likes_user", "user_id"),)

    comment: Mapped["Comment"] = relationship("Comment", back_populates="likes")
    user: Mapped["User"] = relationship("User")


class CommentDislike(Base):
    """评论点踩模型，记录用户对评论的点踩关系。"""

    __tablename__ = "comment_dislikes"

    comment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_comment_dislikes_user", "user_id"),)

    comment: Mapped["Comment"] = relationship("Comment", back_populates="dislikes")
    user: Mapped["User"] = relationship("User")
