"""专辑相关的 Pydantic Schema 定义，包含输出模型和请求模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# 嵌套输出模型
# ---------------------------------------------------------------------------

class AlbumAuthorOut(BaseModel):
    """专辑作者输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    ordinal: int


class AlbumMusicOut(BaseModel):
    """专辑内嵌套的音乐输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    is_vip: bool
    hot: int
    play_count: int
    cover_icon_url: str | None = None
    ordinal: int


class TagOut(BaseModel):
    """标签输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ---------------------------------------------------------------------------
# 专辑输出模型
# ---------------------------------------------------------------------------

class AlbumOut(BaseModel):
    """专辑详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    source: str | None = None
    collect_count: int
    play_count: int
    hot: int
    cover_icon_url: str | None = None
    cover_url: str | None = None
    authors: list[AlbumAuthorOut] = []
    musics: list[AlbumMusicOut] = []
    emotion_tags: list[TagOut] = []
    interest_tags: list[TagOut] = []
    created_at: datetime
    updated_at: datetime
    is_collected_by_me: bool = False

    @field_validator("authors", mode="before")
    @classmethod
    def _flatten_authors(cls, v):
        """将关联的作者对象展平为字典列表。"""
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

    @field_validator("musics", mode="before")
    @classmethod
    def _flatten_musics(cls, v):
        """将关联的音乐对象展平为字典列表。"""
        if not v:
            return []
        return [
            {
                "id": am.music.id,
                "title": am.music.title,
                "is_vip": am.music.is_vip,
                "hot": am.music.hot,
                "play_count": am.music.play_count,
                "cover_icon_url": am.music.cover_icon_url,
                "ordinal": am.ordinal,
            }
            for am in v
        ]

    @field_validator("emotion_tags", mode="before")
    @classmethod
    def _flatten_emotion_tags(cls, v):
        """将关联的情绪标签对象展平为字典列表。"""
        if not v:
            return []
        return [
            {"id": et.emotion_tag.id, "name": et.emotion_tag.name}
            for et in v
        ]

    @field_validator("interest_tags", mode="before")
    @classmethod
    def _flatten_interest_tags(cls, v):
        """将关联的兴趣标签对象展平为字典列表。"""
        if not v:
            return []
        return [
            {"id": it.interest_tag.id, "name": it.interest_tag.name}
            for it in v
        ]


class AlbumListOut(BaseModel):
    """专辑列表项输出（精简）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    hot: int
    play_count: int
    cover_icon_url: str | None = None
    created_at: datetime


class AdminAlbumListItem(AlbumListOut):
    """管理员专辑列表项，在 AlbumListOut 基础上增加作者、歌曲数和收藏数。"""

    authors: list[AlbumAuthorOut] = []
    music_count: int
    collect_count: int


class PaginatedAlbumListOut(BaseModel):
    """专辑列表分页响应 Schema。"""

    items: list[AlbumListOut]
    total: int


class PaginatedAdminAlbumListOut(BaseModel):
    """管理员专辑列表分页响应 Schema。"""

    items: list[AdminAlbumListItem]
    total: int


class AlbumCreate(BaseModel):
    """管理员创建专辑的请求体（不含文件）。"""

    title: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=500)
    source: str | None = Field(None, max_length=50)
    author_ids: list[int] | None = None


class AlbumUpdate(BaseModel):
    """管理员修改专辑信息的请求体（不含文件和标签编辑）。"""

    title: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=500)
    source: str | None = Field(None, max_length=50)
    author_ids: list[int] | None = None
