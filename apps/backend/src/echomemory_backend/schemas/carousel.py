"""轮播推图 Schema 定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CarouselItemOut(BaseModel):
    """轮播推图公开响应。"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str  # "music" | "album"
    target_id: int
    title: str
    description: str
    image_url: str | None = None
    sort_order: int


class CarouselItemCreate(BaseModel):
    """管理员创建推图请求。"""
    type: str = Field(..., pattern="^(music|album)$", description="推送种类")
    target_id: int = Field(..., gt=0)
    title: str = Field(..., min_length=1, max_length=128)
    description: str = Field("", max_length=256)


class CarouselItemUpdate(BaseModel):
    """管理员修改推图请求。"""
    title: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=256)


class ReorderRequest(BaseModel):
    """调整推图顺序请求。"""
    ids: list[str] = Field(..., min_length=1)
