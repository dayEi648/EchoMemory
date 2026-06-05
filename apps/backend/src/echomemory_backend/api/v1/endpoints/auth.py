from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from echomemory_backend.api.deps import ActiveUser, SessionDep
from echomemory_backend.core.redis_client import (
    delete_refresh_token,
    generate_refresh_token,
    get_refresh_token_user_id,
    store_refresh_token,
)
from echomemory_backend.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import (
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserMeOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: int) -> Token:
    access_token = create_access_token(subject=user_id)
    refresh_token = generate_refresh_token()
    store_refresh_token(refresh_token, user_id)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(db: SessionDep, user_in: UserCreate) -> Token:
    stmt = select(User).where(User.username == user_in.username)
    if db.execute(stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )
    if user_in.email:
        stmt = select(User).where(User.email == user_in.email)
        if db.execute(stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

    user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
        nickname=user_in.nickname,
        email=user_in.email,
        phone=user_in.phone,
        gender=user_in.gender,
        birth=user_in.birth,
        bio=user_in.bio,
        city_id=user_in.city_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return _issue_tokens(user.id)


@router.post("/login", response_model=Token)
def login(db: SessionDep, user_in: UserLogin) -> Token:
    stmt = select(User).where(User.username == user_in.username)
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(user_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deleted",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_tokens(user.id)


@router.post("/refresh", response_model=Token)
def refresh_token(db: SessionDep, data: TokenRefresh) -> Token:
    user_id = get_refresh_token_user_id(data.refresh_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = db.get(User, int(user_id))
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    delete_refresh_token(data.refresh_token)
    return _issue_tokens(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: TokenRefresh) -> None:
    delete_refresh_token(data.refresh_token)
    return None


@router.get("/me", response_model=UserMeOut)
def get_me(current_user: ActiveUser) -> User:
    return current_user
