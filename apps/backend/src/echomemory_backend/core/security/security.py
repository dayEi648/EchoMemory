"""认证与授权相关的安全工具模块，提供密码哈希、JWT 创建与解码等功能。"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from echomemory_backend.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希密码匹配。"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """为给定密码生成 bcrypt 哈希值。"""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int,
    version: int = 0,
    expires_delta: timedelta | None = None,
) -> str:
    """为指定主体（用户 ID）创建 JWT access token。

    Args:
        subject: 要编码到 token 中的用户标识符。
        version: 用户 token version，用于强制失效机制。
        expires_delta: 可选的自定义过期时间增量，默认使用配置值。

    Returns:
        编码后的 JWT 字符串。
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access", "ver": version}
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解码并校验 JWT access token。

    Args:
        token: 待解码的 JWT 字符串。

    Returns:
        校验通过则返回解码后的 payload 字典，否则返回 None。
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
