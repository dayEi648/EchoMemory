from fastapi import APIRouter, HTTPException, status

from echomemory_backend.api.deps import ActiveUser, SessionDep, TokenDep
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
from echomemory_backend.services.user_service import BusinessError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(db: SessionDep, user_in: UserCreate) -> Token:
    """Register a new user and return an access/refresh token pair."""
    try:
        return register_user(db, user_in)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/login", response_model=Token)
def login(db: SessionDep, user_in: UserLogin) -> Token:
    """Authenticate a user and return an access/refresh token pair."""
    try:
        return authenticate_user(db, user_in.username, user_in.password)
    except BusinessError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=Token)
def refresh_token(db: SessionDep, data: TokenRefresh) -> Token:
    """Rotate a refresh token and issue a new token pair."""
    try:
        return refresh_user_token(db, data.refresh_token)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: TokenRefresh, token: TokenDep) -> None:
    """Invalidate the refresh token and blacklist the current access token."""
    logout_user(data.refresh_token, token)
    return None


@router.get("/me", response_model=UserMeOut)
def get_me(current_user: ActiveUser) -> User:
    """Return the current authenticated user's profile."""
    return current_user
