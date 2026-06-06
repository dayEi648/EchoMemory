from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class TagOut(BaseModel):
    """标签输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ---------------------------------------------------------------------------
# 音乐输出模型
# ---------------------------------------------------------------------------

class MusicOut(BaseModel):
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

    @field_validator("authors", mode="before")
    @classmethod
    def _flatten_authors(cls, v):
        if not v:
            return []
        return [
            {
                "id": a.author.id,
                "username": a.author.username,
                "nickname": a.author.nickname,
                "avatar_url": a.author.avatar_url,
                "ordinal": a.ordinal,
            }
            for a in v
        ]

    @field_validator("instruments", mode="before")
    @classmethod
    def _flatten_instruments(cls, v):
        if not v:
            return []
        return [
            {"id": mi.instrument.id, "name": mi.instrument.name}
            for mi in v
        ]

    @field_validator("emotion_tags", mode="before")
    @classmethod
    def _flatten_emotion_tags(cls, v):
        if not v:
            return []
        return [
            {"id": et.emotion_tag.id, "name": et.emotion_tag.name}
            for et in v
        ]

    @field_validator("interest_tags", mode="before")
    @classmethod
    def _flatten_interest_tags(cls, v):
        if not v:
            return []
        return [
            {"id": it.interest_tag.id, "name": it.interest_tag.name}
            for it in v
        ]


class MusicListOut(BaseModel):
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

    @field_validator("authors", mode="before")
    @classmethod
    def _flatten_authors(cls, v):
        if not v:
            return []
        return [
            {
                "id": a.author.id,
                "username": a.author.username,
                "nickname": a.author.nickname,
                "avatar_url": a.author.avatar_url,
                "ordinal": a.ordinal,
            }
            for a in v
        ]


# ---------------------------------------------------------------------------
# 音乐更新模型
# ---------------------------------------------------------------------------

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
