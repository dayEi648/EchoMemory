"""收藏与发布相关的 Pydantic Schema 定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from echomemory_backend.schemas.album import AlbumListOut
from echomemory_backend.schemas.music import MusicListOut
from echomemory_backend.schemas.playlist import PlaylistListOut


class MusicCollectionOut(BaseModel):
    """音乐收藏项输出。"""

    model_config = ConfigDict(from_attributes=True)

    music: MusicListOut
    created_at: datetime


class AlbumCollectionOut(BaseModel):
    """专辑收藏项输出。"""

    model_config = ConfigDict(from_attributes=True)

    album: AlbumListOut
    created_at: datetime


class PlaylistCollectionOut(BaseModel):
    """歌单收藏项输出。"""

    model_config = ConfigDict(from_attributes=True)

    playlist: PlaylistListOut
    created_at: datetime


class ReleaseOut(BaseModel):
    """已发布音乐标记项输出。"""

    model_config = ConfigDict(from_attributes=True)

    music: MusicListOut
    created_at: datetime


class PaginatedMusicCollectionOut(BaseModel):
    """音乐收藏列表分页响应 Schema。"""

    items: list[MusicCollectionOut]
    total: int


class PaginatedAlbumCollectionOut(BaseModel):
    """专辑收藏列表分页响应 Schema。"""

    items: list[AlbumCollectionOut]
    total: int


class PaginatedPlaylistCollectionOut(BaseModel):
    """歌单收藏列表分页响应 Schema。"""

    items: list[PlaylistCollectionOut]
    total: int


class PaginatedReleaseOut(BaseModel):
    """已发布音乐列表分页响应 Schema。"""

    items: list[ReleaseOut]
    total: int
