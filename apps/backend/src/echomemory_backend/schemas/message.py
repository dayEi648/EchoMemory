"""私信会话与消息相关的 Pydantic Schema 定义。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessagePeerOut(BaseModel):
    """会话/消息中嵌套的对端用户精简信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    is_official: bool = False


class DirectMessageOut(BaseModel):
    """单条私信输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    """会话列表项输出 Schema。"""

    id: int
    peer: MessagePeerOut
    last_message: DirectMessageOut | None = None
    unread_count: int
    is_blocked_by_me: bool = False
    is_blocking_me: bool = False
    updated_at: datetime


class PaginatedConversationOut(BaseModel):
    """会话列表分页响应 Schema。"""

    items: list[ConversationOut]
    total: int


class PaginatedDirectMessageOut(BaseModel):
    """私信消息分页响应 Schema。消息按时间倒序返回，前端反转后渲染即可。"""

    items: list[DirectMessageOut]
    total: int


class DirectMessageCreate(BaseModel):
    """发送私信的请求体。"""

    content: str = Field(..., min_length=1, max_length=2000)
