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
