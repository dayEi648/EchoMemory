"""AI 对话相关的 Pydantic Schema 定义。"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AIConversationMessageRole = Literal["system", "human", "ai", "tool"]


class AIConversationMessageOut(BaseModel):
    """单条消息输出 Schema。

    role 支持 system、human、ai、tool；
    tool 类型消息会额外包含 tool_call_id 与 name。
    """

    model_config = ConfigDict(from_attributes=True)

    role: AIConversationMessageRole
    content: str | list[dict[str, Any]]
    reasoning_content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    artifact: dict[str, Any] | None = None
    additional_kwargs: dict[str, Any] | None = None
    created_at: datetime | None = None


class AIConversationOut(BaseModel):
    """AI 会话列表项/详情输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    model: str
    status: int
    thread_id: str
    updated_at: datetime
    created_at: datetime


class PaginatedAIConversationOut(BaseModel):
    """AI 会话分页响应 Schema。"""

    items: list[AIConversationOut]
    total: int


class AIConversationMessagesOut(BaseModel):
    """AI 会话消息列表响应 Schema。"""

    messages: list[AIConversationMessageOut]


class AIConversationCreate(BaseModel):
    """创建 AI 会话的请求体。"""

    title: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=50)
    first_message: str | None = Field(default=None, max_length=4000)
    stream: bool = False


class AIConversationWithFirstMessageOut(BaseModel):
    """创建会话并附带首条 AI 回复的响应 Schema。"""

    conversation: AIConversationOut
    ai_message: AIConversationMessageOut | None = None


class AIConversationMessageCreate(BaseModel):
    """发送消息的请求体。"""

    content: str = Field(..., min_length=1, max_length=4000)
    stream: bool = False
    confirmation_token: str | None = Field(default=None, max_length=2048)


class AIConversationTitleUpdate(BaseModel):
    """手动更新会话标题的请求体。"""

    title: str = Field(..., min_length=1, max_length=200)


class AIStreamChunkOut(BaseModel):
    """流式响应 SSE 数据包 Schema。"""

    type: Literal["content", "reasoning", "attachment", "done", "error"]
    data: str = ""
    model: str | None = None
    meta: dict[str, Any] | None = None
