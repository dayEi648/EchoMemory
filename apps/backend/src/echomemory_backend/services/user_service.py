from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomemory_backend.models.user import User, UserFollow
from echomemory_backend.schemas.user import UserCreate, UserUpdate


class BusinessError(Exception):
    """Raised when a business rule is violated.

    Attributes:
        detail: Human-readable error message.
        status_code: Suggested HTTP status code for the error.
    """

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    """Fetch a user by username."""
    stmt = select(User).where(User.username == username)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email address."""
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    """Fetch a user by phone number."""
    stmt = select(User).where(User.phone == phone)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, user_in: UserCreate, password_hash: str) -> User:
    """Create a new user after validating uniqueness constraints.

    Args:
        db: SQLAlchemy session.
        user_in: User creation schema.
        password_hash: Pre-hashed password string.

    Raises:
        BusinessError: If username, email or phone already exists.
    """
    if get_user_by_username(db, user_in.username):
        raise BusinessError("Username already registered", 409)
    if user_in.email and get_user_by_email(db, user_in.email):
        raise BusinessError("Email already registered", 409)
    if user_in.phone and get_user_by_phone(db, user_in.phone):
        raise BusinessError("Phone already registered", 409)

    user = User(
        username=user_in.username,
        password_hash=password_hash,
        nickname=user_in.nickname,
        email=user_in.email,
        phone=user_in.phone,
        gender=user_in.gender,
        birth=user_in.birth,
        bio=user_in.bio,
        city_id=user_in.city_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("Username, email or phone already registered", 409)
    db.refresh(user)
    return user


def update_user_profile(
    db: Session, current_user: User, user_in: UserUpdate
) -> User:
    """Update the current user's profile.

    Args:
        db: SQLAlchemy session.
        current_user: The user to update.
        user_in: Update payload.

    Raises:
        BusinessError: If the new email or phone is already taken.
    """
    if user_in.email is not None and user_in.email != current_user.email:
        if get_user_by_email(db, user_in.email):
            raise BusinessError("Email already registered", 409)
        current_user.email = user_in.email

    if user_in.phone is not None and user_in.phone != current_user.phone:
        if get_user_by_phone(db, user_in.phone):
            raise BusinessError("Phone already registered", 409)
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("Email or phone already registered", 409)
    db.refresh(current_user)
    return current_user


def follow_user(db: Session, follower_id: int, followee_id: int) -> None:
    """Create a follow relationship.

    Raises:
        BusinessError: On self-follow, missing target, or duplicate follow.
    """
    if follower_id == followee_id:
        raise BusinessError("Cannot follow yourself", 400)

    target = get_user_by_id(db, followee_id)
    if not target or target.is_deleted:
        raise BusinessError("User not found", 404)

    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    if db.execute(stmt).scalar_one_or_none():
        raise BusinessError("Already following this user", 409)

    follow = UserFollow(follower_id=follower_id, followee_id=followee_id)
    db.add(follow)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("Already following this user", 409)


def unfollow_user(db: Session, follower_id: int, followee_id: int) -> None:
    """Remove a follow relationship.

    Raises:
        BusinessError: If the follow relationship does not exist.
    """
    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    follow = db.execute(stmt).scalar_one_or_none()
    if not follow:
        raise BusinessError("Not following this user", 404)
    db.delete(follow)
    db.commit()


def get_followees(
    db: Session, user_id: int, limit: int, offset: int
) -> list[User]:
    """Return the list of users that *user_id* follows."""
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


def get_followers(
    db: Session, user_id: int, limit: int, offset: int
) -> list[User]:
    """Return the list of users that follow *user_id*."""
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


def update_user_avatar(db: Session, user: User, avatar_url: str) -> User:
    """Update the user's avatar URL.

    Args:
        db: SQLAlchemy session.
        user: The user to update.
        avatar_url: The new avatar URL returned by OSS.

    Returns:
        The updated user instance.
    """
    user.avatar_url = avatar_url
    db.commit()
    db.refresh(user)
    return user


def search_users(
    db: Session,
    q: str | None,
    limit: int,
    offset: int,
    status: int | None = None,
    role: int | None = None,
) -> list[User]:
    """Search users with optional filters."""
    stmt = select(User).where(User.is_deleted == False)
    if status is not None:
        stmt = stmt.where(User.status == status)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if q:
        stmt = stmt.where(
            (User.username.ilike(f"%{q}%")) | (User.nickname.ilike(f"%{q}%"))
        )
    stmt = stmt.order_by(desc(User.exp)).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())
