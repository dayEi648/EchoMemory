"""API 依赖注入模块，提供数据库会话、用户认证与权限校验的 FastAPI 依赖。"""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions.codes import HttpStatus

from echomemory_backend.core.clients.redis_client import (
    get_user_token_version,
    is_access_token_blacklisted,
)
from echomemory_backend.core.security.security import decode_access_token
from echomemory_backend.db.session import AsyncSessionLocal
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncSession:
    """提供一个异步 SQLAlchemy Session，使用结束后自动关闭。"""
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


SessionDep = Annotated[AsyncSession, Depends(get_db)]
"""数据库会话依赖类型，用于在路由中注入异步 SQLAlchemy Session。"""

TokenDep = Annotated[str, Depends(oauth2_scheme)]
"""JWT Token 依赖类型，用于从请求中提取 OAuth2 Bearer Token。"""


async def get_current_user(db: SessionDep, token: TokenDep) -> User:
    """通过 JWT access token 解析当前用户。

    校验 token 黑名单状态、token version，解码 token，并确认用户存在且未被软删除。
    """
    if await is_access_token_blacklisted(token):
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token version 校验：若用户 token version 已递增，旧 token 立即失效
    token_version = payload.get("ver")
    current_version = await get_user_token_version(user_id_int)
    if token_version != current_version:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id_int)
    if user is None:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_deleted:
        raise HTTPException(
            status_code=HttpStatus.UNAUTHORIZED,
            detail="User account has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
"""当前已认证用户依赖类型，自动校验 token 并注入用户对象。"""


async def get_current_active_user(current_user: CurrentUser) -> User:
    """确保当前用户账号处于活跃状态（未被封禁或暂停）。"""
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=HttpStatus.FORBIDDEN,
            detail="User account is not active",
        )
    return current_user


ActiveUser = Annotated[User, Depends(get_current_active_user)]
"""当前活跃用户依赖类型，确保用户账号未被封禁。"""


async def require_admin(current_user: ActiveUser) -> User:
    """要求当前用户具有 admin 或 super-admin 权限。"""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=HttpStatus.FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
"""管理员用户依赖类型，要求用户具有 admin 或 super-admin 权限。"""


oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)


async def get_current_user_optional(
    db: SessionDep,
    token: str | None = Depends(oauth2_scheme_optional),
) -> User | None:
    """可选地解析当前用户。未提供 token 或 token 无效时返回 None。"""
    if token is None:
        return None
    try:
        return await get_current_user(db, token)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
"""可选用户依赖类型，未登录时返回 None 而非抛出 401。"""
