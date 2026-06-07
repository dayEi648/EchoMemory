from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserTagOut(BaseModel):
    """用户标签偏好输出（情感/兴趣通用）。"""

    model_config = ConfigDict(from_attributes=True)

    tag_id: int
    name: str
    created_at: datetime
