from sqlalchemy.orm import Session

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


def _issue_tokens(user_id: int) -> Token:
    """Issue a new access token and refresh token pair."""
    access_token = create_access_token(subject=user_id)
    refresh_token = generate_refresh_token()
    store_refresh_token(refresh_token, user_id)
    return Token(access_token=access_token, refresh_token=refresh_token)


def register_user(db: Session, user_in: UserCreate) -> Token:
    """Register a new user and return an initial token pair.

    Args:
        db: SQLAlchemy session.
        user_in: User creation schema.

    Raises:
        BusinessError: If uniqueness constraints are violated.
    """
    password_hash = get_password_hash(user_in.password)
    user = create_user(db, user_in, password_hash)
    return _issue_tokens(user.id)


def authenticate_user(db: Session, username: str, password: str) -> Token:
    """Authenticate a user and return a token pair.

    Args:
        db: SQLAlchemy session.
        username: Login username.
        password: Plain-text password.

    Raises:
        BusinessError: If credentials are invalid or account is disabled.
    """
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise BusinessError("Incorrect username or password", 401)
    if user.is_deleted:
        raise BusinessError("User account has been deleted", 401)
    if user.status == UserStatus.BANNED:
        raise BusinessError("User account is banned", 401)
    return _issue_tokens(user.id)


def refresh_user_token(db: Session, refresh_token: str) -> Token:
    """Rotate a refresh token and issue a new token pair.

    Args:
        db: SQLAlchemy session.
        refresh_token: The existing refresh token string.

    Raises:
        BusinessError: If the token is invalid or the user is disabled.
    """
    user_id = get_refresh_token_user_id(refresh_token)
    if user_id is None:
        raise BusinessError("Invalid or expired refresh token", 401)

    user = get_user_by_id(db, int(user_id))
    if not user or user.is_deleted:
        raise BusinessError("User not found", 401)
    if user.status == UserStatus.BANNED:
        raise BusinessError("User account is banned", 401)

    delete_refresh_token(refresh_token)
    return _issue_tokens(user.id)


def logout_user(refresh_token: str, access_token: str | None = None) -> None:
    """Invalidate a refresh token and optionally blacklist the access token.

    Args:
        refresh_token: The refresh token to invalidate.
        access_token: Optional access token to blacklist.
    """
    delete_refresh_token(refresh_token)
    if access_token:
        blacklist_access_token(access_token)
