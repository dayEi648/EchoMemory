"""通知相关的 Pydantic Schema 定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationActorOut(BaseModel):
    """通知中嵌套的发起人精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    is_official: bool = False


class NotificationOut(BaseModel):
    """通知详情输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: int
    target_type: str
    target_id: int
    is_read: bool
    extra: dict
    created_at: datetime
    actor: NotificationActorOut | None = None


class PaginatedNotificationOut(BaseModel):
    """通知列表分页响应 Schema。"""

    items: list[NotificationOut]
    total: int


class UnreadSummaryOut(BaseModel):
    """未读汇总响应 Schema，供铃铛入口快速获取小红点状态。"""

    notification_unread: int
    message_unread: int
