"""认证相关 API 端点，提供用户注册、登录、Token 刷新、登出及当前用户信息查询。"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from echomemory_backend.api.deps import ActiveUser, SessionDep, TokenDep
from echomemory_backend.api.v1.endpoints._upload_helpers import upload_optional_image
from echomemory_backend.core import oss_client
from echomemory_backend.core.config import settings
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import (
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserMeOut,
)
from echomemory_backend.services.auth_service import (
    authenticate_user,
    logout_user,
    refresh_user_token,
    register_user,
)
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.core.redis_client import check_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _parse_user_create_form(
    username: str = Form(..., min_length=3, max_length=32),
    nickname: str = Form(..., min_length=1, max_length=32),
    password: str = Form(..., min_length=6, max_length=128),
    email: str | None = Form(None),
    phone: str | None = Form(None, max_length=20),
    gender: int = Form(0, ge=0, le=2),
    birth: str | None = Form(None),
    bio: str | None = Form(None),
    city: str | None = Form(None),
) -> UserCreate:
    """将 multipart form 字段解析为 UserCreate Schema。"""
    data = {
        "username": username,
        "nickname": nickname,
        "password": password,
        "gender": gender,
    }
    if email is not None:
        data["email"] = email
    if phone is not None:
        data["phone"] = phone
    if birth is not None:
        data["birth"] = birth
    if bio is not None:
        data["bio"] = bio
    if city is not None:
        data["city"] = city
    return UserCreate(**data)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    db: SessionDep,
    user_in: Annotated[UserCreate, Depends(_parse_user_create_form)],
    avatar: UploadFile | None = File(None),
) -> Token:
    """注册新用户，并返回 access token 与 refresh token 对。

    可选上传头像图片，服务端自动压缩并上传到 OSS。
    """
    avatar_url = await upload_optional_image(
        avatar,
        folder=settings.oss_avatar_prefix,
        prefix="register",
        detail_name="Avatar",
    )

    try:
        return await register_user(db, user_in, avatar_url)
    except BusinessError:
        if avatar_url:
            await oss_client.delete_object_by_url(avatar_url)
        raise


@router.post("/login", response_model=Token)
async def login(
    db: SessionDep,
    user_in: UserLogin,
    request: Request,
) -> Token:
    """验证用户身份，并返回 access token 与 refresh token 对。

    同一 IP 地址 60 秒内最多允许 5 次登录请求。
    """
    client_ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(
        f"login:{client_ip}", max_requests=5, window_seconds=60
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, please try again later",
        )
    return await authenticate_user(db, user_in.username, user_in.password)


@router.post("/refresh", response_model=Token)
async def refresh_token(db: SessionDep, data: TokenRefresh) -> Token:
    """轮换 refresh token 并签发新的 token 对。"""
    return await refresh_user_token(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: TokenRefresh, token: TokenDep) -> None:
    """使 refresh token 失效，并将当前 access token 加入黑名单。"""
    await logout_user(data.refresh_token, token)
    return None


@router.get("/me", response_model=UserMeOut)
async def get_me(current_user: ActiveUser) -> User:
    """返回当前已认证用户的个人资料。"""
    return current_user
