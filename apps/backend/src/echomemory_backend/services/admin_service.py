from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from echomemory_backend.core.redis_client import increment_user_token_version
from echomemory_backend.core.utils import parse_iso8601_duration
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import UserAdminUpdate, UserBanAction
from echomemory_backend.core.exceptions import BusinessError
from echomemory_backend.services.user_service import get_user_by_id


async def list_users(
    db: AsyncSession,
    status: int | None,
    role: int | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[User]:
    """以管理员筛选条件列出用户。

    Args:
        db: SQLAlchemy 异步 Session。
        status: 按用户状态筛选；为 None 时不按状态过滤。
        role: 按用户角色筛选；为 None 时不按角色过滤。
        q: 搜索关键词，支持对用户名和昵称进行模糊匹配；为 None 时不按关键词过滤。
        limit: 返回结果数量上限。
        offset: 分页偏移量。

    Returns:
        符合条件的用户实例列表。
    """
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
    stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)
    return list((await db.execute(stmt)).scalars().all())


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
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    # 除非自己是 super-admin，否则不能修改 super-admin
    if user.role == UserRole.SUPER_ADMIN and admin.role != UserRole.SUPER_ADMIN:
        raise BusinessError("Cannot modify super-admin user", 403)

    # 除非自己是 super-admin，否则不能将任何人提升为 super-admin
    if (
        user_in.role is not None
        and user_in.role == UserRole.SUPER_ADMIN
        and admin.role != UserRole.SUPER_ADMIN
    ):
        raise BusinessError("Cannot promote user to super-admin", 403)

    # 记录是否修改了影响账户可用性的字段
    should_invalidate_tokens = False

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
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)
    if user.role == UserRole.SUPER_ADMIN and admin.role != UserRole.SUPER_ADMIN:
        raise BusinessError("Cannot ban super-admin user", 403)

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
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = await get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    if user.role == UserRole.SUPER_ADMIN and admin.role != UserRole.SUPER_ADMIN:
        raise BusinessError("Cannot unban super-admin user", 403)

    user.status = UserStatus.ACTIVE
    user.banned_at = None
    user.ban_duration = None

    await db.commit()
    await db.refresh(user)
    return user
