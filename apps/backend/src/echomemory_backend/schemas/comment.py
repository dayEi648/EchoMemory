from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CommentUserOut(BaseModel):
    """评论中嵌套的用户精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None


class CommentOut(BaseModel):
    """评论详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    user: CommentUserOut
    like_count: int
    dislike_count: int
    reply_count: int
    parent_id: int | None = None
    root_id: int | None = None
    is_nested_reply: bool
    created_at: datetime

    @field_validator("user", mode="before")
    @classmethod
    def _flatten_user(cls, v):
        if v is None:
            return None
        return {
            "id": v.id,
            "username": v.username,
            "nickname": v.nickname,
            "avatar_url": v.avatar_url,
        }


class CommentCreate(BaseModel):
    """发表评论的请求体。"""

    target_type: str
    target_id: int
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: int | None = None
