from fastapi import APIRouter, HTTPException, Query, status

from echomemory_backend.api.deps import ActiveUser, AdminUser, SessionDep
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import (
    FollowCreate,
    FolloweeOut,
    FollowerOut,
    UserAdminUpdate,
    UserBanAction,
    UserMeOut,
    UserPublicOut,
    UserSearchOut,
    UserUpdate,
)
from echomemory_backend.services import admin_service
from echomemory_backend.services.user_service import BusinessError
from echomemory_backend.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserMeOut)
def update_me(
    db: SessionDep, current_user: ActiveUser, user_in: UserUpdate
) -> User:
    """Update the current user's own profile."""
    try:
        return user_service.update_user_profile(db, current_user, user_in)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{user_id}", response_model=UserPublicOut)
def get_user(db: SessionDep, user_id: int) -> User:
    """Fetch a public user profile by ID."""
    user = user_service.get_user_by_id(db, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get("/", response_model=list[UserSearchOut])
def search_users(
    db: SessionDep,
    q: str | None = Query(None, description="Search by username or nickname"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """Search users with optional keyword filter."""
    return user_service.search_users(db, q=q, limit=limit, offset=offset)


@router.post("/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    """Follow another user."""
    try:
        user_service.follow_user(db, current_user.id, follow_in.followee_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return None


@router.post("/unfollow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    """Unfollow a user."""
    try:
        user_service.unfollow_user(db, current_user.id, follow_in.followee_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return None


@router.get("/{user_id}/followees", response_model=list[FolloweeOut])
def get_followees(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """List users that the given user follows."""
    return user_service.get_followees(db, user_id, limit=limit, offset=offset)


@router.get("/{user_id}/followers", response_model=list[FollowerOut])
def get_followers(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """List users that follow the given user."""
    return user_service.get_followers(db, user_id, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@router.get("/admin/list", response_model=list[UserMeOut])
def admin_list_users(
    db: SessionDep,
    admin: AdminUser,
    status: int | None = Query(None, ge=0, le=3),
    role: int | None = Query(None, ge=0, le=3),
    q: str | None = Query(None, description="Search by username or nickname"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    """List users with admin filters."""
    return admin_service.list_users(
        db, status=status, role=role, q=q, limit=limit, offset=offset
    )


@router.patch("/{user_id}/admin", response_model=UserMeOut)
def admin_update_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    user_in: UserAdminUpdate,
) -> User:
    """Update a user as an admin."""
    try:
        return admin_service.update_user_as_admin(db, admin, user_id, user_in)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{user_id}/ban", response_model=UserMeOut)
def admin_ban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    action: UserBanAction,
) -> User:
    """Ban a user."""
    try:
        return admin_service.ban_user(db, admin, user_id, action)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/{user_id}/unban", response_model=UserMeOut)
def admin_unban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
) -> User:
    """Unban a user."""
    try:
        return admin_service.unban_user(db, admin, user_id)
    except BusinessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
