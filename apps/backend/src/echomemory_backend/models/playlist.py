"""定义歌单相关的数据库 ORM 模型。"""

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
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.dictionary import EmotionTag, InterestTag
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.user import User


class Playlist(Base):
    """歌单模型，表示用户创建的音乐播放列表。"""

    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    collect_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    play_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    forward_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hot: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_like: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ---- 内容审核字段 ----
    safety_score: Mapped[int | None] = mapped_column(Integer)
    recommendation_score: Mapped[int | None] = mapped_column(Integer)
    safety_level: Mapped[str | None] = mapped_column(String(16))
    recommendation_level: Mapped[str | None] = mapped_column(String(16))
    moderation_status: Mapped[str | None] = mapped_column(String(16))
    moderation_reason: Mapped[str | None] = mapped_column(Text)
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deletion_reason: Mapped[str | None] = mapped_column(String(32))
    # ---- 内容审核字段结束 ----
    cover_icon_url: Mapped[str | None] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "collect_count >= 0", name="chk_playlists_collect_count_nonnegative"
        ),
        CheckConstraint("play_count >= 0", name="chk_playlists_play_count_nonnegative"),
        CheckConstraint("forward_count >= 0", name="chk_playlists_forward_count_nonnegative"),
        CheckConstraint("hot >= 0 AND hot <= 1000", name="chk_playlists_hot"),
        CheckConstraint(
            "comment_count >= 0", name="chk_playlists_comment_count_nonnegative"
        ),
        Index(
            "idx_playlists_unique_user_like",
            "user_id",
            unique=True,
            postgresql_where=is_like.is_(True),
        ),
        Index("idx_playlists_user_id", "user_id"),
        Index("idx_playlists_hot", desc("hot")),
        Index("idx_playlists_play_count", desc("play_count")),
        Index("idx_playlists_collect_count", desc("collect_count")),
        Index("idx_playlists_created_at", desc("created_at")),
        Index(
            "idx_playlists_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    user: Mapped["User"] = relationship("User", back_populates="playlists")
    musics: Mapped[list["PlaylistMusic"]] = relationship(
        "PlaylistMusic", back_populates="playlist"
    )
    emotion_tags: Mapped[list["PlaylistEmotionTag"]] = relationship(
        "PlaylistEmotionTag", back_populates="playlist"
    )
    interest_tags: Mapped[list["PlaylistInterestTag"]] = relationship(
        "PlaylistInterestTag", back_populates="playlist"
    )


class PlaylistMusic(Base):
    """歌单-音乐关联模型，记录歌单中包含的音乐及其顺序。"""

    __tablename__ = "playlist_musics"

    playlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "ordinal >= 0", name="chk_playlist_musics_ordinal_nonnegative"
        ),
        UniqueConstraint("playlist_id", "ordinal", name="uq_playlist_musics_ordinal"),
    )

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="musics")
    music: Mapped["Music"] = relationship("Music")


class PlaylistEmotionTag(Base):
    """歌单-情感标签关联模型，记录歌单关联的情感标签。"""

    __tablename__ = "playlist_emotion_tags"

    playlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    emotion_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("emotion_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_playlist_emotion_tags_tag", "emotion_tag_id"),)

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="emotion_tags")
    emotion_tag: Mapped["EmotionTag"] = relationship("EmotionTag")


class PlaylistInterestTag(Base):
    """歌单-兴趣标签关联模型，记录歌单关联的兴趣标签。"""

    __tablename__ = "playlist_interest_tags"

    playlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    interest_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interest_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_playlist_interest_tags_tag", "interest_tag_id"),)

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="interest_tags")

    interest_tag: Mapped["InterestTag"] = relationship("InterestTag")