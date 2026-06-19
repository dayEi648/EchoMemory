"""系统日志相关 Pydantic Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SystemLogOut(BaseModel):
    """系统日志列表项输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    level: str
    logger: str
    message: str
    request_method: str | None = None
    request_path: str | None = None
    has_stack_trace: bool

    @staticmethod
    def from_orm(log) -> "SystemLogOut":  # type: ignore[no-untyped-def]
        return SystemLogOut(
            id=log.id,
            created_at=log.created_at,
            level=log.level,
            logger=log.logger,
            message=log.message,
            request_method=log.request_method,
            request_path=log.request_path,
            has_stack_trace=log.stack_trace is not None and log.stack_trace != "",
        )


class SystemLogDetailOut(BaseModel):
    """系统日志详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    level: str
    logger: str
    message: str
    stack_trace: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    request_body: str | None = None
    response_body: str | None = None
    extra: str | None = None


class PaginatedSystemLogOut(BaseModel):
    """系统日志分页输出。"""

    items: list[SystemLogOut]
    total: int


class SystemLogListParams(BaseModel):
    """系统日志列表查询参数。"""

    level: str | None = Field(None, description="日志等级: WARNING/ERROR/CRITICAL")
    start_time: datetime | None = Field(None, description="起始时间（ISO 8601）")
    end_time: datetime | None = Field(None, description="结束时间（ISO 8601）")
    q: str | None = Field(None, description="消息关键词模糊搜索")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)
