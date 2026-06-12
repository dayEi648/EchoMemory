"""用户业务逻辑服务层。

提供用户查询、创建、资料更新、关注/取关以及用户搜索等操作。
"""

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.models.enums import NotificationType
from echomemory_backend.models.user import User, UserFollow
from echomemory_backend.schemas.user import UserCreate, UserUpdate
from echomemory_backend.services.notification_service import create_notification
from echomemory_backend.services.playlist_service import create_default_like_playlist


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """根据主键查询用户。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 要查询的用户主键。

    Returns:
        找到的用户实例，不存在时返回 None。
    """
    return await db.get(User, user_id)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """根据用户名查询用户。

    Args:
        db: SQLAlchemy 异步 Session。
        username: 要查询的用户名。

    Returns:
        找到的用户实例，不存在时返回 None。
    """
    stmt = select(User).where(User.username == username)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """根据邮箱地址查询用户。

    Args:
        db: SQLAlchemy 异步 Session。
        email: 要查询的邮箱地址。

    Returns:
        找到的用户实例，不存在时返回 None。
    """
    stmt = select(User).where(User.email == email)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """根据手机号查询用户。

    Args:
        db: SQLAlchemy 异步 Session。
        phone: 要查询的手机号。

    Returns:
        找到的用户实例，不存在时返回 None。
    """
    stmt = select(User).where(User.phone == phone)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: UserCreate, password_hash: str, avatar_url: str | None = None) -> User:
    """在验证唯一性约束后创建新用户。

    Args:
        db: SQLAlchemy AsyncSession。
        user_in: 用户创建 Schema。
        password_hash: 已哈希的密码字符串。
        avatar_url: 可选的头像 URL。

    Raises:
        BusinessError: 用户名、邮箱或手机号已存在时抛出。
    """
    if await get_user_by_username(db, user_in.username):
        raise BusinessError("用户名已被注册", 409)
    if user_in.email and await get_user_by_email(db, user_in.email):
        raise BusinessError("邮箱已被注册", 409)
    if user_in.phone and await get_user_by_phone(db, user_in.phone):
        raise BusinessError("手机号已被注册", 409)

    user = User(
        username=user_in.username,
        password_hash=password_hash,
        nickname=user_in.nickname,
        email=user_in.email,
        phone=user_in.phone,
        gender=user_in.gender,
        birth=user_in.birth,
        bio=user_in.bio,
        city=user_in.city,
        avatar_url=avatar_url,
    )
    db.add(user)
    try:
        await db.flush()
        await create_default_like_playlist(db, user.id, commit=False)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("用户名、邮箱或手机号已被注册", 409)
    await db.refresh(user)
    return user


async def update_user_profile(
    db: AsyncSession, current_user: User, user_in: UserUpdate, avatar_url: str | None = None
) -> User:
    """更新当前用户的个人资料。

    注意：若未来支持修改密码，必须在此处调用
    `increment_user_token_version(current_user.id)` 以强制该用户所有已签发 token 失效。

    Args:
        db: SQLAlchemy AsyncSession。
        current_user: 待更新的用户。
        user_in: 更新内容。
        avatar_url: 可选的新头像 URL。

    Raises:
        BusinessError: 新邮箱或手机号已被占用时抛出。
    """
    if user_in.email is not None and user_in.email != current_user.email:
        if await get_user_by_email(db, user_in.email):
            raise BusinessError("邮箱已被注册", 409)
        current_user.email = user_in.email

    if user_in.phone is not None and user_in.phone != current_user.phone:
        if await get_user_by_phone(db, user_in.phone):
            raise BusinessError("手机号已被注册", 409)
        current_user.phone = user_in.phone

    if user_in.nickname is not None:
        current_user.nickname = user_in.nickname
    if user_in.gender is not None:
        current_user.gender = user_in.gender
    if user_in.birth is not None:
        current_user.birth = user_in.birth
    if user_in.bio is not None:
        current_user.bio = user_in.bio
    if user_in.city is not None:
        current_user.city = user_in.city
    if avatar_url is not None:
        current_user.avatar_url = avatar_url

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("邮箱或手机号已被注册", 409)
    await db.refresh(current_user)
    return current_user


async def follow_user(db: AsyncSession, follower_id: int, followee_id: int) -> None:
    """创建关注关系。

    Raises:
        BusinessError: 自己关注自己、目标用户不存在或重复关注时抛出。
    """
    if follower_id == followee_id:
        raise BusinessError("不能关注自己", 400)

    target = await get_user_by_id(db, followee_id)
    if not target or target.is_deleted:
        raise BusinessError("用户不存在", 404)

    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise BusinessError("已关注该用户", 409)

    follow = UserFollow(follower_id=follower_id, followee_id=followee_id)
    db.add(follow)
    await create_notification(
        db,
        recipient_id=followee_id,
        actor_id=follower_id,
        type=NotificationType.FOLLOW,
        target_type="user",
        target_id=followee_id,
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("已关注该用户", 409)


async def is_following(db: AsyncSession, follower_id: int, followee_id: int) -> bool:
    """判断 follower 是否已关注 followee。

    Args:
        db: SQLAlchemy 异步 Session。
        follower_id: 关注者主键。
        followee_id: 被关注者主键。

    Returns:
        已关注返回 True，否则返回 False。
    """
    stmt = select(UserFollow).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id == followee_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def get_followed_user_ids(
    db: AsyncSession, follower_id: int, followee_ids: list[int]
) -> set[int]:
    """批量查询 follower 已关注的用户 ID 集合。

    Args:
        db: SQLAlchemy 异步 Session。
        follower_id: 关注者主键。
        followee_ids: 待查询的被关注者主键列表。

    Returns:
        follower 已关注的 followee_id 集合。
    """
    if not followee_ids:
        return set()
    stmt = select(UserFollow.followee_id).where(
        UserFollow.follower_id == follower_id,
        UserFollow.followee_id.in_(followee_ids),
    )
    return set((await db.execute(stmt)).scalars().all())


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
        raise BusinessError("未关注该用户", 404)
    await db.delete(follow)
    await db.commit()


async def get_followees(
    db: AsyncSession, user_id: int, limit: int, offset: int
) -> dict[str, object]:
    """返回 user_id 所关注的用户列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 查询目标的用户主键。
        limit: 返回结果数量上限。
        offset: 分页偏移量。

    Returns:
        {"items": 用户实例列表, "total": 总记录数}。
    """
    where_clause = [
        UserFollow.follower_id == user_id,
        User.is_deleted == False,
    ]
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.followee_id == User.id)
        .where(*where_clause)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count())
            .select_from(UserFollow)
            .join(User, UserFollow.followee_id == User.id)
            .where(*where_clause)
        )
    ).scalar_one()
    return {"items": items, "total": total}


async def get_followers(
    db: AsyncSession, user_id: int, limit: int, offset: int
) -> dict[str, object]:
    """返回关注 user_id 的用户列表。

    Args:
        db: SQLAlchemy 异步 Session。
        user_id: 查询目标的用户主键。
        limit: 返回结果数量上限。
        offset: 分页偏移量。

    Returns:
        {"items": 用户实例列表, "total": 总记录数}。
    """
    where_clause = [
        UserFollow.followee_id == user_id,
        User.is_deleted == False,
    ]
    stmt = (
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(*where_clause)
        .order_by(desc(UserFollow.created_at))
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(
            select(func.count())
            .select_from(UserFollow)
            .join(User, UserFollow.follower_id == User.id)
            .where(*where_clause)
        )
    ).scalar_one()
    return {"items": items, "total": total}


async def search_users(
    db: AsyncSession,
    q: str | None,
    limit: int,
    offset: int,
    status: int | None = None,
    role: int | None = None,
) -> dict[str, object]:
    """按可选条件搜索用户。

    Args:
        db: SQLAlchemy 异步 Session。
        q: 搜索关键词，支持对用户名和昵称进行模糊匹配；为 None 时不按关键词过滤。
        limit: 返回结果数量上限。
        offset: 分页偏移量。
        status: 按用户状态筛选；为 None 时不按状态过滤。
        role: 按用户角色筛选；为 None 时不按角色过滤。

    Returns:
        {"items": 符合条件的用户实例列表, "total": 总记录数}。
    """
    where_clause = [User.is_deleted == False]
    if status is not None:
        where_clause.append(User.status == status)
    if role is not None:
        where_clause.append(User.role == role)
    if q:
        escaped_q = q.replace("%", "\\%").replace("_", "\\_")
        where_clause.append(
            (User.username.ilike(f"%{escaped_q}%", escape="\\"))
            | (User.nickname.ilike(f"%{escaped_q}%", escape="\\"))
        )

    stmt = (
        select(User)
        .where(*where_clause)
        .order_by(desc(User.exp))
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).scalars().all())
    total = (
        await db.execute(select(func.count()).where(*where_clause))
    ).scalar_one()
    return {"items": items, "total": total}
