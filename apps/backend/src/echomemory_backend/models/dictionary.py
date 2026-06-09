"""系统字典/配置相关的 ORM 模型定义。"""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.music import Music, MusicInstrument


class LevelConfig(Base):
    """等级配置表，记录用户等级与所需经验值的映射关系。"""
    __tablename__ = "level_config"

    level: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    min_exp: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (Index("idx_level_config_min_exp", "min_exp"),)


class Language(Base):
    """语言字典表，存储音乐作品的语言分类。"""

    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    musics: Mapped[list["Music"]] = relationship("Music", back_populates="language")


class Style(Base):
    """风格字典表，存储音乐作品的风格分类。"""

    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    musics: Mapped[list["Music"]] = relationship("Music", back_populates="style")


class Instrument(Base):
    """乐器字典表，存储音乐作品涉及的乐器类型。"""

    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    music_associations: Mapped[list["MusicInstrument"]] = relationship(
        "MusicInstrument", back_populates="instrument"
    )


class EmotionTag(Base):
    """情感标签字典表，用于标记音乐的情感属性。"""

    __tablename__ = "emotion_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class InterestTag(Base):
    """兴趣标签字典表，用于标记用户的兴趣偏好。"""

    __tablename__ = "interest_tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
