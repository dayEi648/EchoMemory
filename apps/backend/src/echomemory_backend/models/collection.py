from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, desc, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from echomemory_backend.db.base import Base


class UserMusicRelease(Base):
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
