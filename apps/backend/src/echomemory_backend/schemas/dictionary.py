"""字典模块的 Pydantic Schema 定义。"""

from pydantic import BaseModel, ConfigDict, Field


class DictionaryItemCreate(BaseModel):
    """创建字典项的请求体。"""

    name: str = Field(..., min_length=1, max_length=50)


class DictionaryItemUpdate(BaseModel):
    """更新字典项的请求体。"""

    name: str | None = Field(None, min_length=1, max_length=50)


class DictionaryItemOut(BaseModel):
    """字典项输出模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DictionaryItemListOut(BaseModel):
    """字典项分页列表输出模型。"""

    items: list[DictionaryItemOut]
    total: int
