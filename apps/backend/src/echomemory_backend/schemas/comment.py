"""评论相关的 Pydantic Schema 定义。"""

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
    liked_by_me: bool = False
    disliked_by_me: bool = False

    @field_validator("user", mode="before")
    @classmethod
    def _flatten_user(cls, v):
        """将 user ORM 对象扁平化为字典。

        Args:
            v: 用户 ORM 对象或 None。

        Returns:
            包含用户精简信息的字典，或 None。
        """
        if v is None:
            return None
        return {
            "id": v.id,
            "username": v.username,
            "nickname": v.nickname,
            "avatar_url": v.avatar_url,
        }


class PaginatedCommentOut(BaseModel):
    """评论列表分页响应 Schema。"""

    items: list[CommentOut]
    total: int


class CommentCreate(BaseModel):
    """发表评论的请求体。"""

    target_type: str
    target_id: int
    content: str = Field(..., min_length=1, max_length=2000)
    parent_id: int | None = None
