"""空间动态相关的 Pydantic Schema 定义。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class SpacePostImageOut(BaseModel):
    """动态图片输出。"""

    model_config = ConfigDict(from_attributes=True)

    image_url: str
    ordinal: int


class SpacePostOut(BaseModel):
    """动态详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str | None = None
    is_private: bool
    comment_count: int
    images: list[SpacePostImageOut] = []
    created_at: datetime
    updated_at: datetime

    @field_validator("images", mode="before")
    @classmethod
    def _flatten_images(cls, v: Any) -> list[dict]:
        if not v:
            return []
        return [
            {"image_url": img.image_url, "ordinal": img.ordinal}
            for img in v
        ]


class SpacePostListOut(BaseModel):
    """动态列表项输出（精简）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str | None = None
    is_private: bool
    comment_count: int
    images: list[SpacePostImageOut] = []
    created_at: datetime

    @field_validator("images", mode="before")
    @classmethod
    def _flatten_images(cls, v: Any) -> list[dict]:
        if not v:
            return []
        return [
            {"image_url": img.image_url, "ordinal": img.ordinal}
            for img in v
        ]


class PaginatedSpacePostListOut(BaseModel):
    """动态列表分页响应 Schema。"""

    items: list[SpacePostListOut]
    total: int
