from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.user import User


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50))
    collect_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    play_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hot: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    cover_icon_url: Mapped[str | None] = mapped_column(String(500))
    cover_url: Mapped[str | None] = mapped_column(String(500))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "collect_count >= 0", name="chk_albums_collect_count_nonnegative"
        ),
        CheckConstraint("play_count >= 0", name="chk_albums_play_count_nonnegative"),
        CheckConstraint("hot >= 0 AND hot <= 1000", name="chk_albums_hot"),
        Index("idx_albums_hot", desc("hot"), postgresql_where=is_deleted.is_(False)),
        Index(
            "idx_albums_play_count",
            desc("play_count"),
            postgresql_where=is_deleted.is_(False),
        ),
        Index(
            "idx_albums_collect_count",
            desc("collect_count"),
            postgresql_where=is_deleted.is_(False),
        ),
        Index(
            "idx_albums_created_at",
            desc("created_at"),
            postgresql_where=is_deleted.is_(False),
        ),
        Index(
            "idx_albums_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
            postgresql_where=is_deleted.is_(False),
        ),
    )

    authors: Mapped[list["AlbumAuthor"]] = relationship(
        "AlbumAuthor", back_populates="album"
    )
    musics: Mapped[list["AlbumMusic"]] = relationship("AlbumMusic", back_populates="album")
    emotion_tags: Mapped[list["AlbumEmotionTag"]] = relationship(
        "AlbumEmotionTag", back_populates="album"
    )
    interest_tags: Mapped[list["AlbumInterestTag"]] = relationship(
        "AlbumInterestTag", back_populates="album"
    )


class AlbumAuthor(Base):
    __tablename__ = "album_authors"

    album_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "ordinal >= 0", name="chk_album_authors_ordinal_nonnegative"
        ),
        UniqueConstraint("album_id", "ordinal", name="uq_album_authors_ordinal"),
        Index("idx_album_authors_author", "author_id"),
    )

    album: Mapped["Album"] = relationship("Album", back_populates="authors")
    author: Mapped["User"] = relationship("User")


class AlbumMusic(Base):
    __tablename__ = "album_musics"

    album_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
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
            "ordinal >= 0", name="chk_album_musics_ordinal_nonnegative"
        ),
        UniqueConstraint("music_id", name="uq_album_musics_music"),
        UniqueConstraint("album_id", "ordinal", name="uq_album_musics_ordinal"),
    )

    album: Mapped["Album"] = relationship("Album", back_populates="musics")
    music: Mapped["Music"] = relationship("Music")


class AlbumEmotionTag(Base):
    __tablename__ = "album_emotion_tags"

    album_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    emotion_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("emotion_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_album_emotion_tags_tag", "emotion_tag_id"),)

    album: Mapped["Album"] = relationship("Album", back_populates="emotion_tags")


class AlbumInterestTag(Base):
    __tablename__ = "album_interest_tags"

    album_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    interest_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interest_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_album_interest_tags_tag", "interest_tag_id"),)

    album: Mapped["Album"] = relationship("Album", back_populates="interest_tags")
