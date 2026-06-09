"""定义用户收藏相关的数据库模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base

if TYPE_CHECKING:
    from echomemory_backend.models.album import Album
    from echomemory_backend.models.music import Music
    from echomemory_backend.models.playlist import Playlist
    from echomemory_backend.models.user import User


class UserMusicRelease(Base):
    """用户音乐发布关联模型，记录用户发布的音乐。"""
    __tablename__ = "user_music_releases"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_music_releases_user_time", "user_id", desc("created_at")),
    )

    user: Mapped["User"] = relationship("User")
    music: Mapped["Music"] = relationship("Music")


class UserMusicCollection(Base):
    """用户音乐收藏模型，记录用户收藏的单曲。"""
    __tablename__ = "user_music_collections"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    music_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("musics.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_music_collections_user_time", "user_id", desc("created_at")),
    )

    user: Mapped["User"] = relationship("User")
    music: Mapped["Music"] = relationship("Music")


class UserAlbumCollection(Base):
    """用户专辑收藏模型，记录用户收藏的专辑。"""
    __tablename__ = "user_album_collections"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    album_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_user_album_collections_user_time", "user_id", desc("created_at")),
    )

    user: Mapped["User"] = relationship("User")
    album: Mapped["Album"] = relationship("Album")


class UserPlaylistCollection(Base):
    """用户歌单收藏模型，记录用户收藏的歌单。"""
    __tablename__ = "user_playlist_collections"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    playlist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "idx_user_playlist_collections_user_time", "user_id", desc("created_at")
        ),
    )

    user: Mapped["User"] = relationship("User")
    playlist: Mapped["Playlist"] = relationship("Playlist")
