from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.redis_client import (
    blacklist_access_token,
    delete_refresh_token,
    generate_refresh_token,
    get_refresh_token_user_id,
    store_refresh_token,
)
from echomemory_backend.core.security import create_access_token, get_password_hash, verify_password
from echomemory_backend.models.enums import UserStatus
from echomemory_backend.schemas.user import Token, UserCreate
from echomemory_backend.services.user_service import BusinessError, create_user, get_user_by_id, get_user_by_username


async def _issue_tokens(user_id: int) -> Token:
    """签发新的 access token 与 refresh token 对。"""
    access_token = create_access_token(subject=user_id)
    refresh_token = generate_refresh_token()
    await store_refresh_token(refresh_token, user_id)
    return Token(access_token=access_token, refresh_token=refresh_token)


async def register_user(db: AsyncSession, user_in: UserCreate) -> Token:
    """注册新用户并返回初始 token 对。

    Args:
        db: SQLAlchemy AsyncSession。
        user_in: 用户创建 Schema。

    Raises:
        BusinessError: 唯一性约束冲突时抛出。
    """
    password_hash = get_password_hash(user_in.password)
    user = await create_user(db, user_in, password_hash)
    return await _issue_tokens(user.id)


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Token:
    """验证用户身份并返回 token 对。

    Args:
        db: SQLAlchemy AsyncSession。
        username: 登录用户名。
        password: 明文密码。

    Raises:
        BusinessError: 凭据无效或账号被禁用时抛出。
    """
    user = await get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise BusinessError("Incorrect username or password", 401)
    if user.is_deleted:
        raise BusinessError("User account has been deleted", 401)
    if user.status == UserStatus.BANNED:
        raise BusinessError("User account is banned", 401)
    return await _issue_tokens(user.id)


async def refresh_user_token(db: AsyncSession, refresh_token: str) -> Token:
    """轮换 refresh token 并签发新的 token 对。

    Args:
        db: SQLAlchemy AsyncSession。
        refresh_token: 现有的 refresh token 字符串。

    Raises:
        BusinessError: token 无效或用户被禁用时抛出。
    """
    user_id = await get_refresh_token_user_id(refresh_token)
    if user_id is None:
        raise BusinessError("Invalid or expired refresh token", 401)

    user = await get_user_by_id(db, int(user_id))
    if not user or user.is_deleted:
        raise BusinessError("User not found", 401)
    if user.status == UserStatus.BANNED:
        raise BusinessError("User account is banned", 401)

    await delete_refresh_token(refresh_token)
    return await _issue_tokens(user.id)


async def logout_user(refresh_token: str, access_token: str | None = None) -> None:
    """使 refresh token 失效，并可选地将 access token 加入黑名单。

    Args:
        refresh_token: 要失效的 refresh token。
        access_token: 可选，要加入黑名单的 access token。
    """
    await delete_refresh_token(refresh_token)
    if access_token:
        await blacklist_access_token(access_token)
