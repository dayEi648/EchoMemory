from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator

from echomemory_backend.core.utils import timedelta_to_iso8601_duration


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    nickname: str = Field(..., min_length=1, max_length=32)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: int = Field(default=0, ge=0, le=2)
    birth: date | None = None
    bio: str | None = None
    city_id: int | None = None


class UserUpdate(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=32)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: int | None = Field(None, ge=0, le=2)
    birth: date | None = None
    bio: str | None = None
    city_id: int | None = None
    avatar_url: str | None = Field(None, max_length=500)


class UserAdminUpdate(BaseModel):
    role: Literal[0, 1, 2, 3] | None = None
    status: Literal[0, 1, 2, 3] | None = None
    safety_score: int | None = Field(None, ge=0, le=10)
    is_verified: bool | None = None
    exp: int | None = Field(None, ge=0)
    banned_at: datetime | None = None
    ban_duration: str | None = None


class UserBanAction(BaseModel):
    status: Literal[1, 2, 3]
    ban_duration: str | None = None

    @field_validator("ban_duration")
    @classmethod
    def validate_ban_duration(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("P"):
            raise ValueError(
                "ban_duration must be an ISO 8601 duration string starting with P"
            )
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    gender: int
    role: int
    level: int
    exp: int
    city_id: int | None = None
    birth: date | None = None
    bio: str | None = None
    is_verified: bool
    like_count: int
    avatar_url: str | None = None
    created_at: datetime | None = None


class UserMeOut(UserOut):
    email: EmailStr | None = None
    phone: str | None = None
    status: int
    safety_score: int
    last_login_at: datetime | None = None
    banned_at: datetime | None = None
    ban_duration: str | None = None

    @field_serializer("ban_duration")
    def serialize_ban_duration(self, value: timedelta | None) -> str | None:
        return timedelta_to_iso8601_duration(value)


class UserPublicOut(UserOut):
    pass


class FollowCreate(BaseModel):
    followee_id: int = Field(..., gt=0)


class FolloweeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int
    is_verified: bool


class FollowerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int
    is_verified: bool


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str | None = None


class UserSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    avatar_url: str | None = None
    level: int
    is_verified: bool
