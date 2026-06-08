from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.music import Music, MusicInstrument


class LevelConfig(Base):
    __tablename__ = "level_config"

    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    min_exp: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (Index("idx_level_config_min_exp", "min_exp"),)


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    musics: Mapped[list["Music"]] = relationship("Music", back_populates="language")


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    musics: Mapped[list["Music"]] = relationship("Music", back_populates="style")


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    music_associations: Mapped[list["MusicInstrument"]] = relationship(
        "MusicInstrument", back_populates="instrument"
    )


class EmotionTag(Base):
    __tablename__ = "emotion_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class InterestTag(Base):
    __tablename__ = "interest_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
