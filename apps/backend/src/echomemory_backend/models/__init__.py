from echomemory_backend.db.base import Base
from echomemory_backend.models.enums import NotificationType, UserRole, UserStatus
from echomemory_backend.models.album import (
    Album,
    AlbumAuthor,
    AlbumEmotionTag,
    AlbumInterestTag,
    AlbumMusic,
)
from echomemory_backend.models.collection import (
    UserAlbumCollection,
    UserMusicRelease,
    UserPlaylistCollection,
)
from echomemory_backend.models.comment import (
    Comment,
    CommentDislike,
    CommentLike,
)
from echomemory_backend.models.dictionary import (
    EmotionTag,
    Instrument,
    InterestTag,
    Language,
    LevelConfig,
    Style,
)
from echomemory_backend.models.message import (
    Conversation,
    DirectMessage,
    UserBlock,
)
from echomemory_backend.models.music import (
    Music,
    MusicAuthor,
    MusicEmotionTag,
    MusicInstrument,
    MusicInterestTag,
)
from echomemory_backend.models.notification import Notification
from echomemory_backend.models.play_history import PlayHistory
from echomemory_backend.models.playlist import (
    Playlist,
    PlaylistEmotionTag,
    PlaylistInterestTag,
    PlaylistMusic,
)
from echomemory_backend.models.recommendation import (
    UserDailyRecommendation,
    UserRadarRecommendation,
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
    UserLanguage,
    UserStyle,
)
from echomemory_backend.models.vector_document import VectorDocument

__all__ = [
    "Base",
    "Album",
    "AlbumAuthor",
    "AlbumEmotionTag",
    "AlbumInterestTag",
    "AlbumMusic",
    "Comment",
    "CommentDislike",
    "CommentLike",
    "Conversation",
    "DirectMessage",
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
    "Notification",
    "NotificationType",
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
    "UserBlock",
    "UserDailyRecommendation",
    "UserEmotionTag",
    "UserFollow",
    "UserInterestTag",
    "UserLanguage",
    "UserMusicRelease",
    "UserPlaylistCollection",
    "UserRadarRecommendation",
    "UserRole",
    "UserStatus",
    "UserStyle",
    "VectorDocument",
]
