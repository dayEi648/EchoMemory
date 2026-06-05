from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from echomemory_backend.core.redis_client import is_access_token_blacklisted
from echomemory_backend.core.security import decode_access_token
from echomemory_backend.db.session import SessionLocal
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Session:
    """Yield a SQLAlchemy session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]


def get_current_user(db: SessionDep, token: TokenDep) -> User:
    """Resolve the current user from the JWT access token.

    Validates token blacklist status, decodes the token, and checks
    that the user exists and has not been soft-deleted.
    """
    if is_access_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id_int)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUser) -> User:
    """Ensure the current user account is active (not banned)."""
    if current_user.status == UserStatus.BANNED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is banned",
        )
    return current_user


ActiveUser = Annotated[User, Depends(get_current_active_user)]


def require_admin(current_user: ActiveUser) -> User:
    """Require that the current user has admin or super-admin privileges."""
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
