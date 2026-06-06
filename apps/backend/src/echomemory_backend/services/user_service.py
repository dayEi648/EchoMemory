from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.models.user import User, UserFollow
from echomemory_backend.schemas.user import UserCreate, UserUpdate


class BusinessError(Exception):
    """业务规则被违反时抛出。

    Attributes:
        detail: 人类可读的错误信息。
        status_code: 建议的 HTTP 状态码。
    """

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """根据主键查询用户。"""
    return await db.get(User, user_id)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """根据用户名查询用户。"""
    stmt = select(User).where(User.username == username)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """根据邮箱地址查询用户。"""
    stmt = select(User).where(User.email == email)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """根据手机号查询用户。"""
    stmt = select(User).where(User.phone == phone)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate, password_hash: str) -> User:
    """在验证唯一性约束后创建新用户。

    Args:
        db: SQLAlchemy AsyncSession。
        user_in: 用户创建 Schema。
        password_hash: 已哈希的密码字符串。

    Raises:
        BusinessError: 用户名、邮箱或手机号已存在时抛出。
    """
    if await get_user_by_username(db, user_in.username):
        raise BusinessError("Username already registered", 409)
    if user_in.email and await get_user_by_email(db, user_in.email):
        raise BusinessError("Email already registered", 409)
    if user_in.phone and await get_user_by_phone(db, user_in.phone):
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
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("Username, email or phone already registered", 409)
    await db.refresh(user)
    return user


async def update_user_profile(
    db: AsyncSession, current_user: User, user_in: UserUpdate
) -> User:
    """更新当前用户的个人资料。

    Args:
        db: SQLAlchemy AsyncSession。
        current_user: 待更新的用户。
        user_in: 更新内容。

    Raises:
        BusinessError: 新邮箱或手机号已被占用时抛出。
    """
    if user_in.email is not None and user_in.email != current_user.email:
        if await get_user_by_email(db, user_in.email):
            raise BusinessError("Email already registered", 409)
        current_user.email = user_in.email

    if user_in.phone is not None and user_in.phone != current_user.phone:
        if await get_user_by_phone(db, user_in.phone):
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
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("Email or phone already registered", 409)
    await db.refresh(current_user)
    return current_user


async def follow_user(db: AsyncSession, follower_id: int, followee_id: int) -> None:
    """创建关注关系。

    Raises:
        BusinessError: 自己关注自己、目标用户不存在或重复关注时抛出。
    """
    if follower_id == followee_id:
        raise BusinessError("Cannot follow yourself", 400)

    target = await get_user_by_id(db, followee_id)
    if not target or target.is_deleted:
        raise BusinessError("User not found", 404)

    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise BusinessError("Already following this user", 409)

    follow = UserFollow(follower_id=follower_id, followee_id=followee_id)
    db.add(follow)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("Already following this user", 409)


async def unfollow_user(db: AsyncSession, follower_id: int, followee_id: int) -> None:
    """移除关注关系。

    Raises:
        BusinessError: 关注关系不存在时抛出。
    """
    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    follow = (await db.execute(stmt)).scalar_one_or_none()
    if not follow:
        raise BusinessError("Not following this user", 404)
    await db.delete(follow)
    await db.commit()


async def get_followees(
    db: AsyncSession, user_id: int, limit: int, offset: int
) -> list[User]:
    """返回 user_id 所关注的用户列表。"""
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.followee_id == User.id)
        .where(UserFollow.follower_id == user_id)
        .where(User.is_deleted == False)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_followers(
    db: AsyncSession, user_id: int, limit: int, offset: int
) -> list[User]:
    """返回关注 user_id 的用户列表。"""
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.followee_id == user_id)
        .where(User.is_deleted == False)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def update_user_avatar(db: AsyncSession, user: User, avatar_url: str) -> User:
    """更新用户头像 URL。

    Args:
        db: SQLAlchemy AsyncSession。
        user: 待更新的用户。
        avatar_url: OSS 返回的新头像 URL。

    Returns:
        更新后的用户实例。
    """
    user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return user


async def search_users(
    db: AsyncSession,
    q: str | None,
    limit: int,
    offset: int,
    status: int | None = None,
    role: int | None = None,
) -> list[User]:
    """按可选条件搜索用户。"""
    stmt = select(User).where(User.is_deleted == False)
    if status is not None:
        stmt = stmt.where(User.status == status)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            (User.username.ilike(f"%{escaped_q}%", escape="\\"))
            | (User.nickname.ilike(f"%{escaped_q}%", escape="\\"))
        )
    stmt = stmt.order_by(desc(User.exp)).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())
