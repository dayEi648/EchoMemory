"""内容申诉 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AppealCreate(BaseModel):
    """用户发起申诉的请求体。"""

    content_type: str
    content_id: int
    appeal_reason: str | None = Field(None, max_length=500)


class AppealOut(BaseModel):
    """申诉记录输出。"""

    id: int
    content_type: str
    content_id: int
    user_id: int
    moderation_version: int
    status: str
    appeal_reason: str | None = None
    admin_note: str | None = None
    reviewer_user_id: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class AdminAppealResolve(BaseModel):
    """管理员处理申诉的请求体。"""

    admin_note: str | None = Field(None, max_length=500)
