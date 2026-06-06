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
    """注册新用户，并返回 access token 与 refresh token 对。"""
    try:
        return register_user(db, user_in)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/login", response_model=Token)
def login(db: SessionDep, user_in: UserLogin) -> Token:
    """验证用户身份，并返回 access token 与 refresh token 对。"""
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
    """轮换 refresh token 并签发新的 token 对。"""
    try:
        return refresh_user_token(db, data.refresh_token)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: TokenRefresh, token: TokenDep) -> None:
    """使 refresh token 失效，并将当前 access token 加入黑名单。"""
    logout_user(data.refresh_token, token)
    return None


@router.get("/me", response_model=UserMeOut)
def get_me(current_user: ActiveUser) -> User:
    """返回当前已认证用户的个人资料。"""
    return current_user
