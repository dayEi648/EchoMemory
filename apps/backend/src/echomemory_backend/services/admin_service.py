"""管理员用户管理服务模块，提供用户列表查询、信息修改、封禁与解封等功能。"""

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.redis_client import increment_user_token_version
from echomemory_backend.core.security import get_password_hash
from echomemory_backend.core.utils import parse_iso8601_duration
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import UserAdminCreate, UserAdminUpdate, UserBanAction
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.services.playlist_service import create_default_like_playlist
from echomemory_backend.services.user_service import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_phone,
    get_user_by_username,
)


async def list_users_with_count(
    db: AsyncSession,
    status: int | None,
    role: int | None,
    q: str | None,
    limit: int,
    offset: int,
    sort_by: str = "id",
    sort_order: str = "desc",
    is_deleted: bool | None = False,
) -> tuple[list[User], int]:
    """以管理员筛选条件列出用户并返回总数量。

    Args:
        db: SQLAlchemy 异步 Session。
        status: 按用户状态筛选；为 None 时不按状态过滤。
        role: 按用户角色筛选；为 None 时不按角色过滤。
        q: 搜索关键词，支持对用户名和昵称进行模糊匹配；为 None 时不按关键词过滤。
        limit: 返回结果数量上限。
        offset: 分页偏移量。
        sort_by: 排序字段，支持 created_at、exp、level、like_count。
        sort_order: 排序方向，asc 或 desc。
        is_deleted: 按是否注销（软删除）筛选；为 None 时显示全部，默认为 False 只显示未注销用户。

    Returns:
        包含两个元素的元组：用户实例列表和符合条件的总记录数。
    """
    where_clause: list = []
    if is_deleted is not None:
        where_clause.append(User.is_deleted == is_deleted)
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

    # 查询总数
    count_stmt = select(func.count()).select_from(User).where(*where_clause)
    total = (await db.execute(count_stmt)).scalar_one()

    # 查询列表
    sort_column = getattr(User, sort_by, User.created_at)
    order = desc(sort_column) if sort_order == "desc" else sort_column
    stmt = select(User).where(*where_clause).order_by(order).limit(limit).offset(offset)
    items = list((await db.execute(stmt)).scalars().all())
    return items, total


def _assert_can_manage(admin: User, target: User) -> None:
    """验证管理员是否有权限操作目标用户。

    权限规则：
    - 任何管理员（含超级管理员）都不能对自己执行管理操作
    - 超级管理员不能管理其他超级管理员
    - 管理员只能管理普通用户(0)和VIP(1)
    - 管理员不能管理其他管理员(2)和超级管理员(3)

    Raises:
        BusinessError: 权限不足时抛出 403。
    """
    # 统一禁止管理员对自己执行任何管理操作
    if target.id == admin.id:
        raise BusinessError("无权操作该用户", 403)

    if admin.role == UserRole.SUPER_ADMIN:
        if target.role == UserRole.SUPER_ADMIN:
            raise BusinessError("无权操作该用户", 403)
        return
    if admin.role == UserRole.ADMIN:
        if target.role >= UserRole.ADMIN:
            raise BusinessError("无权操作该用户", 403)
        return
    raise BusinessError("无权操作该用户", 403)


async def create_user_as_admin(db: AsyncSession, admin: User, user_in: UserAdminCreate) -> User:
    """以管理员身份创建新用户。

    权限规则：
    - 超级管理员可以创建任意角色的用户
    - 管理员只能创建普通用户(0)和VIP(1)，不能创建管理员(2)或超级管理员(3)
    - 管理员不能创建与自己同级或更高级别的用户

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行操作的管理员。
        user_in: 用户创建内容。

    Raises:
        BusinessError: 权限不足或唯一性约束冲突时抛出。
    """
    # 权限校验：管理员不能创建同级或更高级别用户
    if admin.role == UserRole.ADMIN and user_in.role >= UserRole.ADMIN:
        raise BusinessError("无权创建该角色的用户", 403)

    # 校验用户名/邮箱/手机唯一性
    if await get_user_by_username(db, user_in.username):
        raise BusinessError("用户名已被注册", 409)
    if user_in.email and await get_user_by_email(db, user_in.email):
        raise BusinessError("邮箱已被注册", 409)
    if user_in.phone and await get_user_by_phone(db, user_in.phone):
        raise BusinessError("手机号已被注册", 409)

    password_hash = get_password_hash(user_in.password)

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
        role=user_in.role,
        status=user_in.status,
        safety_score=user_in.safety_score,
        is_verified=user_in.is_verified,
        exp=user_in.exp,
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


async def update_user_as_admin(
    db: AsyncSession, admin: User, target_user_id: int, user_in: UserAdminUpdate
) -> User:
    """以管理员身份更新用户信息。

    若修改了影响账户可用性的字段（status、role），会自动递增用户 token version，
    强制该用户所有已签发 token 失效。

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行操作的管理员。
        target_user_id: 待修改的用户 ID。
        user_in: 更新内容。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    _assert_can_manage(admin, user)

    # 只有超级管理员才能将用户提升为超级管理员
    if (
        user_in.role is not None
        and user_in.role == UserRole.SUPER_ADMIN
        and admin.role != UserRole.SUPER_ADMIN
    ):
        raise BusinessError("Cannot promote user to super-admin", 403)

    # 记录是否修改了影响账户可用性的字段
    should_invalidate_tokens = False

    # 基本资料字段
    if user_in.nickname is not None:
        user.nickname = user_in.nickname
    if user_in.email is not None and user_in.email != user.email:
        from echomemory_backend.services.user_service import get_user_by_email
        if await get_user_by_email(db, user_in.email):
            raise BusinessError("邮箱已被注册", 409)
        user.email = user_in.email
    if user_in.phone is not None and user_in.phone != user.phone:
        from echomemory_backend.services.user_service import get_user_by_phone
        if await get_user_by_phone(db, user_in.phone):
            raise BusinessError("手机号已被注册", 409)
        user.phone = user_in.phone
    if user_in.gender is not None:
        user.gender = user_in.gender
    if user_in.birth is not None:
        user.birth = user_in.birth
    if user_in.bio is not None:
        user.bio = user_in.bio
    if user_in.city is not None:
        user.city = user_in.city

    # 权限与状态字段
    if user_in.role is not None:
        user.role = user_in.role
        should_invalidate_tokens = True
    if user_in.status is not None:
        user.status = user_in.status
        should_invalidate_tokens = True
    if user_in.safety_score is not None:
        user.safety_score = user_in.safety_score
    if user_in.is_verified is not None:
        user.is_verified = user_in.is_verified
    if user_in.exp is not None:
        user.exp = user_in.exp
    if user_in.banned_at is not None:
        user.banned_at = user_in.banned_at
    if user_in.ban_duration is not None:
        user.ban_duration = parse_iso8601_duration(user_in.ban_duration)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("Invalid user state combination", 400)
    await db.refresh(user)

    # 若修改了 status 或 role，强制该用户所有 token 失效
    if should_invalidate_tokens:
        await increment_user_token_version(target_user_id)

    return user


async def ban_user(db: AsyncSession, admin: User, target_user_id: int, action: UserBanAction) -> User:
    """封禁用户。

    封禁完成后自动递增用户 token version，强制该用户所有已签发 token 失效。

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行操作的管理员。
        target_user_id: 待封禁的用户 ID。
        action: 封禁操作载荷，包含状态与可选封禁时长。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    _assert_can_manage(admin, user)

    user.status = action.status
    user.banned_at = func.now()
    if action.ban_duration is not None:
        user.ban_duration = parse_iso8601_duration(action.ban_duration)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise BusinessError("Invalid ban state or duration", 400)
    await db.refresh(user)

    # 封禁后强制该用户所有 token 失效
    await increment_user_token_version(target_user_id)

    return user


async def unban_user(db: AsyncSession, admin: User, target_user_id: int) -> User:
    """解封用户。

    解封后不自动恢复旧 token 的有效性（用户需重新登录），因此不递减 version。

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行操作的管理员。
        target_user_id: 待解封的用户 ID。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    _assert_can_manage(admin, user)

    user.status = UserStatus.ACTIVE
    user.banned_at = None
    user.ban_duration = None

    await db.commit()
    await db.refresh(user)
    return user


async def get_user_full(db: AsyncSession, admin: User, target_user_id: int) -> User:
    """以管理员身份获取单个用户的完整信息。

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行查询的管理员。
        target_user_id: 待查询的用户 ID。

    Returns:
        目标用户实例。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    _assert_can_manage(admin, user)
    return user


async def hard_delete_user(db: AsyncSession, admin: User, target_user_id: int) -> None:
    """硬删除用户及其所有关联数据。

    由于数据库外键均设置为 ON DELETE CASCADE，删除用户记录会自动级联删除
    其歌单、评论、动态、播放历史、关注关系、收藏等全部关联数据。

    Args:
        db: SQLAlchemy AsyncSession。
        admin: 执行删除的管理员。
        target_user_id: 待删除的用户 ID。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    _assert_can_manage(admin, user)

    await db.delete(user)
    await db.commit()
