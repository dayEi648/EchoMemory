"""歌单相关的 Pydantic Schema 定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echomemory_backend.schemas.mixins import (
    EmotionTagValidatorMixin,
    InterestTagValidatorMixin,
)
from echomemory_backend.schemas.music import MusicListOut, TagOut


class PlaylistUserOut(BaseModel):
    """歌单中嵌套的用户精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None


class PlaylistMusicOut(BaseModel):
    """歌单内嵌套的音乐关联输出。"""

    model_config = ConfigDict(from_attributes=True)

    music: MusicListOut
    ordinal: int

    @field_validator("music", mode="before")
    @classmethod
    def _flatten_music(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        return MusicListOut.model_validate(v).model_dump()


class PlaylistOut(
    EmotionTagValidatorMixin,
    InterestTagValidatorMixin,
    BaseModel,
):
    """歌单详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    is_private: bool
    cover_icon_url: str | None = None
    collect_count: int
    play_count: int
    hot: int
    comment_count: int
    is_like: bool
    is_recommended: bool
    user: PlaylistUserOut
    musics: list[PlaylistMusicOut] = []
    emotion_tags: list[TagOut] = []
    interest_tags: list[TagOut] = []
    created_at: datetime
    updated_at: datetime
    is_collected_by_me: bool = False

    @field_validator("user", mode="before")
    @classmethod
    def _flatten_user(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        return {
            "id": v.id,
            "username": v.username,
            "nickname": v.nickname,
            "avatar_url": v.avatar_url,
        }

    @field_validator("musics", mode="before")
    @classmethod
    def _flatten_musics(cls, v):
        if not v:
            return []
        if isinstance(v[0], dict):
            return v
        return [
            {
                "music": pm.music,
                "ordinal": pm.ordinal,
            }
            for pm in v
        ]


class PlaylistListOut(BaseModel):
    """歌单列表项输出（精简）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_private: bool
    is_like: bool
    cover_icon_url: str | None = None
    user: PlaylistUserOut
    created_at: datetime
    is_collected_by_me: bool = False

    @field_validator("user", mode="before")
    @classmethod
    def _flatten_user(cls, v):
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        return {
            "id": v.id,
            "username": v.username,
            "nickname": v.nickname,
            "avatar_url": v.avatar_url,
        }


class PaginatedPlaylistListOut(BaseModel):
    """歌单列表分页响应 Schema。"""

    items: list[PlaylistListOut]
    total: int


class PlaylistMembershipItemOut(BaseModel):
    """歌单归属项：用于歌曲收藏时的歌单选择器。"""

    id: int
    title: str
    is_private: bool
    is_like: bool
    cover_icon_url: str | None = None
    contains_music: bool


class PaginatedPlaylistMembershipOut(BaseModel):
    """用户歌单归属分页响应 Schema。"""

    items: list[PlaylistMembershipItemOut]
    total: int


class PlaylistUpdate(BaseModel):
    """修改歌单信息的请求体（不含封面替换和标签编辑）。"""

    title: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=500)
    is_private: bool | None = None
