"""定义音乐相关的数据库模型，包括歌曲、作者关联、乐器关联及标签关联等。"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.dictionary import Instrument, Language, Style
    from echomemory_backend.models.user import User


class Music(Base):
    """音乐歌曲主表模型，存储歌曲的基本信息与多媒体资源链接。"""

    __tablename__ = "musics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    style_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("styles.id"))
    language_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("languages.id")
    )
    collect_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hot: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    play_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    file_url: Mapped[str | None] = mapped_column(String(500))
    lyrics_url: Mapped[str | None] = mapped_column(String(500))
    cover_icon_url: Mapped[str | None] = mapped_column(String(500))
    cover_home_url: Mapped[str | None] = mapped_column(String(500))
    cover_play_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "collect_count >= 0", name="chk_musics_collect_count_nonnegative"
        ),
        CheckConstraint("hot >= 0 AND hot <= 1000", name="chk_musics_hot"),
        CheckConstraint(
            "comment_count >= 0", name="chk_musics_comment_count_nonnegative"
        ),
        CheckConstraint("play_count >= 0", name="chk_musics_play_count_nonnegative"),
        Index("idx_musics_release_date", desc("release_date")),
        Index("idx_musics_hot", desc("hot")),
        Index("idx_musics_play_count", desc("play_count")),
        Index("idx_musics_collect_count", desc("collect_count")),
        Index("idx_musics_created_at", desc("created_at")),
        Index("idx_musics_style_id", "style_id"),
        Index("idx_musics_language_id", "language_id"),
        Index(
            "idx_musics_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    style: Mapped["Style | None"] = relationship("Style", back_populates="musics")
    language: Mapped["Language | None"] = relationship("Language", back_populates="musics")
    authors: Mapped[list["MusicAuthor"]] = relationship(
        "MusicAuthor", back_populates="music"
    )
    instruments: Mapped[list["MusicInstrument"]] = relationship(
        "MusicInstrument", back_populates="music"
    )
    emotion_tags: Mapped[list["MusicEmotionTag"]] = relationship(
        "MusicEmotionTag", back_populates="music"
    )
    interest_tags: Mapped[list["MusicInterestTag"]] = relationship(
        "MusicInterestTag", back_populates="music"
    )


class MusicAuthor(Base):
    """音乐与作者的多对多关联模型，记录歌曲的创作者及其排序。"""

    __tablename__ = "music_authors"

    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
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
            "ordinal >= 0", name="chk_music_authors_ordinal_nonnegative"
        ),
        UniqueConstraint("music_id", "ordinal", name="uq_music_authors_ordinal"),
        Index("idx_music_authors_author", "author_id"),
    )

    music: Mapped["Music"] = relationship("Music", back_populates="authors")
    author: Mapped["User"] = relationship("User")


class MusicInstrument(Base):
    """音乐与乐器的多对多关联模型，记录歌曲使用的乐器。"""

    __tablename__ = "music_instruments"

    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_music_instruments_instrument", "instrument_id"),)

    music: Mapped["Music"] = relationship("Music", back_populates="instruments")
    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="music_associations"
    )


class MusicEmotionTag(Base):
    """音乐与情绪标签的多对多关联模型。"""

    __tablename__ = "music_emotion_tags"

    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    emotion_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("emotion_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_music_emotion_tags_tag", "emotion_tag_id"),)

    music: Mapped["Music"] = relationship("Music", back_populates="emotion_tags")
    emotion_tag: Mapped["EmotionTag"] = relationship("EmotionTag")


class MusicInterestTag(Base):
    """音乐与兴趣标签的多对多关联模型。"""

    __tablename__ = "music_interest_tags"

    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    interest_tag_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interest_tags.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("idx_music_interest_tags_tag", "interest_tag_id"),)

    music: Mapped["Music"] = relationship("Music", back_populates="interest_tags")
    interest_tag: Mapped["InterestTag"] = relationship("InterestTag")
