from echomemory_backend.db.base import Base
from echomemory_backend.models.album import (
    Album,
    AlbumAuthor,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
)
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.comment import (
    Comment,
    CommentDislike,
    CommentLike,
)
from echomemory_backend.models.dictionary import (
    City,
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    LevelConfig,
    Style,
)
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.space_post import (
    SpacePost,
    SpacePostImage,
    SpacePostLike,
)
from echomemory_backend.models.user import (
    User,
    UserFollow,
)
from echomemory_backend.models.user_tag import (
    UserEmotionTag,
    UserInterestTag,
)

__all__ = [
    "Base",
    "Album",
    "AlbumAuthor",
    "AlbumEmotionTag",
    "AlbumInterestTag",
    "AlbumMusic",
    "City",
    "Comment",
    "CommentDislike",
    "CommentLike",
    "EmotionTag",
    "Instrument",
    "InterestTag",
    "Language",
    "LevelConfig",
    "Music",
    "MusicAuthor",
    "MusicEmotionTag",
    "MusicInstrument",
    "MusicInterestTag",
    "PlayHistory",
    "Playlist",
    "PlaylistEmotionTag",
    "PlaylistInterestTag",
    "PlaylistMusic",
    "SpacePost",
    "SpacePostImage",
    "SpacePostLike",
    "Style",
    "User",
    "UserAlbumCollection",
    "UserEmotionTag",
    "UserFollow",
    "UserInterestTag",
    "UserMusicCollection",
    "UserMusicRelease",
    "UserPlaylistCollection",
]
