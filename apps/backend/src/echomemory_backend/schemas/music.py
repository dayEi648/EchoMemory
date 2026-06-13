"""音乐模块的 Pydantic Schema 定义，涵盖音乐详情、列表项及更新请求等模型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from echomemory_backend.schemas.mixins import (
    EmotionTagValidatorMixin,
    InterestTagValidatorMixin,
    JoinedAuthorValidatorMixin,
)


# ---------------------------------------------------------------------------
# 嵌套输出模型
# ---------------------------------------------------------------------------

class AuthorOut(BaseModel):
    """音乐作者输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    ordinal: int


class InstrumentOut(BaseModel):
    """乐器输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AlbumBriefOut(BaseModel):
    """专辑简要输出（仅含 ID 与标题）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str


class TagOut(BaseModel):
    """标签输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ---------------------------------------------------------------------------
# 音乐输出模型
# ---------------------------------------------------------------------------

class MusicOut(
    JoinedAuthorValidatorMixin,
    EmotionTagValidatorMixin,
    InterestTagValidatorMixin,
    BaseModel,
):
    """音乐详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_vip: bool
    source: str | None = None
    style: TagOut | None = None
    language: TagOut | None = None
    collect_count: int
    hot: int
    comment_count: int
    play_count: int
    is_published: bool
    release_date: date | None = None
    file_url: str | None = None
    lyrics_url: str | None = None
    cover_icon_url: str | None = None
    cover_home_url: str | None = None
    cover_play_url: str | None = None
    authors: list[AuthorOut] = []
    instruments: list[InstrumentOut] = []
    emotion_tags: list[TagOut] = []
    interest_tags: list[TagOut] = []
    created_at: datetime
    updated_at: datetime
    is_collected_by_me: bool = False

    @field_validator("instruments", mode="before")
    @classmethod
    def _flatten_instruments(cls, v):
        """将关联模型列表展平为乐器输出字典列表。

        已展平的字典列表（如来自缓存）直接透传。
        """
        if not v:
            return []
        if isinstance(v[0], dict):
            return v
        return [
            {"id": mi.instrument.id, "name": mi.instrument.name}
            for mi in v
        ]


class MusicListOut(JoinedAuthorValidatorMixin, BaseModel):
    """音乐列表项输出（精简）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_vip: bool
    hot: int
    play_count: int
    cover_icon_url: str | None = None
    authors: list[AuthorOut] = []
    created_at: datetime


class AdminMusicListOut(
    JoinedAuthorValidatorMixin,
    EmotionTagValidatorMixin,
    InterestTagValidatorMixin,
    BaseModel,
):
    """管理员音乐列表项输出（含上架状态及风格/语言/标签/专辑）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_vip: bool
    is_published: bool
    hot: int
    play_count: int
    cover_icon_url: str | None = None
    style: TagOut | None = None
    language: TagOut | None = None
    authors: list[AuthorOut] = []
    emotion_tags: list[TagOut] = []
    interest_tags: list[TagOut] = []
    albums: list[AlbumBriefOut] = []
    created_at: datetime

    @field_validator("albums", mode="before")
    @classmethod
    def _flatten_albums(cls, v):
        """将关联模型列表展平为专辑简要输出字典列表。

        已展平的字典列表（如来自缓存）直接透传。
        """
        if not v:
            return []
        if isinstance(v[0], dict):
            return v
        return [
            {"id": am.album.id, "title": am.album.title}
            for am in v
        ]


# ---------------------------------------------------------------------------
# 音乐更新模型
# ---------------------------------------------------------------------------

class LyricsOut(BaseModel):
    """歌词文本输出。"""

    content: str


class PaginatedMusicListOut(BaseModel):
    """音乐列表分页响应 Schema。"""

    items: list[MusicListOut]
    total: int


class PaginatedAdminMusicListOut(BaseModel):
    """管理员音乐列表分页响应 Schema。"""

    items: list[AdminMusicListOut]
    total: int


class MusicUpdate(BaseModel):
    """管理员修改音乐信息的请求体（不含文件）。"""

    title: str | None = Field(None, min_length=1, max_length=128)
    is_vip: bool | None = None
    source: str | None = Field(None, max_length=50)
    style_id: int | None = None
    language_id: int | None = None
    release_date: date | None = None
    author_ids: list[int] | None = None
    instrument_ids: list[int] | None = None
    emotion_tag_ids: list[int] | None = None
    interest_tag_ids: list[int] | None = None
