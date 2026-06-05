from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from echomemory_backend.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for the given password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int, expires_delta: timedelta | None = None
) -> str:
    """Create a JWT access token for the given subject (user id).

    Args:
        subject: The user identifier to encode in the token.
        expires_delta: Optional custom expiration delta. Defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT string to decode.

    Returns:
        Decoded payload dict if valid, otherwise None.
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
