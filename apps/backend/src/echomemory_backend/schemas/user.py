"""用户相关 Pydantic Schema 定义。"""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from echomemory_backend.core.utils import parse_iso8601_duration, timedelta_to_iso8601_duration


class UserBase(BaseModel):
    """用户基础信息 Schema。"""

    username: str = Field(..., min_length=3, max_length=32)
    nickname: str = Field(..., min_length=1, max_length=32)


class UserCreate(UserBase):
    """用户注册/创建 Schema。"""

    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: int = Field(default=0, ge=0, le=2)
    birth: date | None = None
    bio: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=50)


class UserUpdate(BaseModel):
    """用户个人信息更新 Schema。"""

    nickname: str | None = Field(None, min_length=1, max_length=32)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: int | None = Field(None, ge=0, le=2)
    birth: date | None = None
    bio: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=50)


class UserAdminUpdate(BaseModel):
    """管理员更新用户信息 Schema。"""

    nickname: str | None = Field(None, min_length=1, max_length=32)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: Literal[0, 1, 2] | None = None
    birth: date | None = None
    bio: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=50)
    role: Literal[0, 1, 2, 3] | None = None
    status: Literal[0, 1, 2, 3] | None = None
    safety_score: int | None = Field(None, ge=0, le=10)
    is_verified: bool | None = None
    exp: int | None = Field(None, ge=0)
    banned_at: datetime | None = None
    ban_duration: str | None = None

    @field_validator("ban_duration")
    @classmethod
    def validate_ban_duration(cls, v: str | None) -> str | None:
        """校验封禁时长是否为合法的 ISO 8601 正时长字符串。"""
        if v is not None:
            if not v.startswith("P"):
                raise ValueError(
                    "ban_duration must be an ISO 8601 duration string starting with P"
                )
            td = parse_iso8601_duration(v)
            if td is not None and td.total_seconds() <= 0:
                raise ValueError("ban_duration must represent a positive duration")
        return v


class UserBanAction(BaseModel):
    """用户封禁操作 Schema。"""

    status: Literal[1, 2, 3]
    ban_duration: str | None = None

    @field_validator("ban_duration")
    @classmethod
    def validate_ban_duration(cls, v: str | None) -> str | None:
        """校验封禁时长是否为合法的 ISO 8601 正时长字符串。"""
        if v is not None:
            if not v.startswith("P"):
                raise ValueError(
                    "ban_duration must be an ISO 8601 duration string starting with P"
                )
            td = parse_iso8601_duration(v)
            if td is not None and td.total_seconds() <= 0:
                raise ValueError("ban_duration must represent a positive duration")
        return v


class UserOut(BaseModel):
    """用户公开信息输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    gender: int
    role: int
    level: int
    exp: int
    city: str | None = None
    birth: date | None = None
    bio: str | None = None
    is_verified: bool
    like_count: int
    avatar_url: str | None = None
    created_at: datetime | None = None


class UserMeOut(UserOut):
    """当前登录用户完整信息输出 Schema。"""

    email: EmailStr | None = None
    phone: str | None = None
    status: int
    safety_score: int
    is_deleted: bool
    last_login_at: datetime | None = None
    banned_at: datetime | None = None
    ban_duration: str | None = None

    @field_serializer("ban_duration")
    def serialize_ban_duration(self, value: timedelta | None) -> str | None:
        """将封禁时长序列化为 ISO 8601 时长字符串。"""
        return timedelta_to_iso8601_duration(value)


class UserPublicOut(UserOut):
    """其他用户公开信息输出 Schema。"""

    pass


class FollowCreate(BaseModel):
    """关注操作请求 Schema。"""

    followee_id: int = Field(..., gt=0)


class FolloweeOut(BaseModel):
    """关注对象（被关注者）列表项输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int
    is_verified: bool


class FollowerOut(BaseModel):
    """粉丝列表项输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int


class PaginatedFolloweeOut(BaseModel):
    """关注列表分页响应 Schema。"""

    items: list[FolloweeOut]
    total: int


class PaginatedFollowerOut(BaseModel):
    """粉丝列表分页响应 Schema。"""

    items: list[FollowerOut]
    total: int


class UserLogin(BaseModel):
    """用户登录请求 Schema。"""

    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)


class Token(BaseModel):
    """认证令牌响应 Schema。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """令牌刷新请求 Schema。"""

    refresh_token: str


class TokenPayload(BaseModel):
    """JWT Payload 解析 Schema。"""

    sub: str | None = None


class UserSearchOut(BaseModel):
    """用户搜索结果列表项输出 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int
    is_verified: bool
    bio: str | None = None


class PaginatedUserSearchOut(BaseModel):
    """用户搜索分页响应 Schema。"""

    items: list[UserSearchOut]
    total: int


class PaginatedUserAdminOut(BaseModel):
    """管理员用户列表分页响应 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    items: list[UserMeOut]
    total: int
