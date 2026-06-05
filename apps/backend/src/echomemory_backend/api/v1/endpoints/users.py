from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import desc, func, select

from echomemory_backend.api.deps import ActiveUser, AdminUser, SessionDep
from echomemory_backend.models.user import User, UserFollow
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

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Self profile
# ---------------------------------------------------------------------------
@router.patch("/me", response_model=UserMeOut)
def update_me(
    db: SessionDep, current_user: ActiveUser, user_in: UserUpdate
) -> User:
    if user_in.email is not None and user_in.email != current_user.email:
        stmt = select(User).where(User.email == user_in.email)
        if db.execute(stmt).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        current_user.email = user_in.email

    if user_in.phone is not None:
        current_user.phone = user_in.phone
    if user_in.nickname is not None:
        current_user.nickname = user_in.nickname
    if user_in.gender is not None:
        current_user.gender = user_in.gender
    if user_in.birth is not None:
        current_user.birth = user_in.birth
    if user_in.bio is not None:
        current_user.bio = user_in.bio
    if user_in.city_id is not None:
        current_user.city_id = user_in.city_id
    if user_in.avatar_url is not None:
        current_user.avatar_url = user_in.avatar_url

    db.commit()
    db.refresh(current_user)
    return current_user


# ---------------------------------------------------------------------------
# Public profile
# ---------------------------------------------------------------------------
@router.get("/{user_id}", response_model=UserPublicOut)
def get_user(db: SessionDep, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@router.get("/", response_model=list[UserSearchOut])
def search_users(
    db: SessionDep,
    q: str | None = Query(None, description="Search by username or nickname"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    stmt = select(User).where(User.is_deleted == False)
    if q:
        stmt = stmt.where(
            (User.username.ilike(f"%{q}%")) | (User.nickname.ilike(f"%{q}%"))
        )
    stmt = stmt.order_by(desc(User.exp)).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Follow
# ---------------------------------------------------------------------------
@router.post("/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    if current_user.id == follow_in.followee_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself",
        )

    target = db.get(User, follow_in.followee_id)
    if not target or target.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    stmt = select(UserFollow).where(
        UserFollow.follower_id == current_user.id,
        UserFollow.followee_id == follow_in.followee_id,
    )
    if db.execute(stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already following this user",
        )

    follow = UserFollow(
        follower_id=current_user.id,
        followee_id=follow_in.followee_id,
    )
    db.add(follow)
    db.commit()
    return None


@router.post("/unfollow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    db: SessionDep, current_user: ActiveUser, follow_in: FollowCreate
) -> None:
    stmt = select(UserFollow).where(
        UserFollow.follower_id == current_user.id,
        UserFollow.followee_id == follow_in.followee_id,
    )
    follow = db.execute(stmt).scalar_one_or_none()
    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this user",
        )
    db.delete(follow)
    db.commit()
    return None


@router.get("/{user_id}/followees", response_model=list[FolloweeOut])
def get_followees(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.followee_id == User.id)
        .where(UserFollow.follower_id == user_id)
        .where(User.is_deleted == False)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/{user_id}/followers", response_model=list[FollowerOut])
def get_followers(
    db: SessionDep,
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[User]:
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.followee_id == user_id)
        .where(User.is_deleted == False)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


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
    stmt = select(User).where(User.is_deleted == False)
    if status is not None:
        stmt = stmt.where(User.status == status)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(
            (User.username.ilike(f"%{q}%")) | (User.nickname.ilike(f"%{q}%"))
        )
    stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


@router.patch("/{user_id}/admin", response_model=UserMeOut)
def admin_update_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    user_in: UserAdminUpdate,
) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role == 3 and admin.role != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify super-admin user",
        )

    if user_in.role is not None:
        user.role = user_in.role
    if user_in.status is not None:
        user.status = user_in.status
    if user_in.safety_score is not None:
        user.safety_score = user_in.safety_score
    if user_in.is_verified is not None:
        user.is_verified = user_in.is_verified
    if user_in.exp is not None:
        user.exp = user_in.exp
    if user_in.banned_at is not None:
        user.banned_at = user_in.banned_at

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/ban", response_model=UserMeOut)
def admin_ban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
    action: UserBanAction,
) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.role == 3 and admin.role != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot ban super-admin user",
        )

    user.status = action.status
    user.banned_at = func.now()

    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/unban", response_model=UserMeOut)
def admin_unban_user(
    db: SessionDep,
    admin: AdminUser,
    user_id: int,
) -> User:
    user = db.get(User, user_id)
    if not user or user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.status = 0
    user.banned_at = None
    user.ban_duration = None

    db.commit()
    db.refresh(user)
    return user
