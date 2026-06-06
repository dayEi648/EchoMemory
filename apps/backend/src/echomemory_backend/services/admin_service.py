from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from echomemory_backend.core.utils import parse_iso8601_duration
from echomemory_backend.models.enums import UserRole, UserStatus
from echomemory_backend.models.user import User
from echomemory_backend.schemas.user import UserAdminUpdate, UserBanAction
from echomemory_backend.services.user_service import BusinessError, get_user_by_id


def list_users(
    db: Session,
    status: int | None,
    role: int | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[User]:
    """以管理员筛选条件列出用户。"""
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


def update_user_as_admin(
    db: Session, admin: User, target_user_id: int, user_in: UserAdminUpdate
) -> User:
    """以管理员身份更新用户信息。

    Args:
        db: SQLAlchemy Session。
        admin: 执行操作的管理员。
        target_user_id: 待修改的用户 ID。
        user_in: 更新内容。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = get_user_by_id(db, target_user_id)
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
    if user_in.ban_duration is not None:
        user.ban_duration = parse_iso8601_duration(user_in.ban_duration)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("Invalid user state combination", 400)
    db.refresh(user)
    return user


def ban_user(db: Session, admin: User, target_user_id: int, action: UserBanAction) -> User:
    """封禁用户。

    Args:
        db: SQLAlchemy Session。
        admin: 执行操作的管理员。
        target_user_id: 待封禁的用户 ID。
        action: 封禁操作载荷，包含状态与可选封禁时长。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)
    if user.role == UserRole.SUPER_ADMIN and admin.role != UserRole.SUPER_ADMIN:
        raise BusinessError("Cannot ban super-admin user", 403)

    user.status = action.status
    user.banned_at = func.now()
    if action.ban_duration is not None:
        user.ban_duration = parse_iso8601_duration(action.ban_duration)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BusinessError("Invalid ban state or duration", 400)
    db.refresh(user)
    return user


def unban_user(db: Session, admin: User, target_user_id: int) -> User:
    """解封用户。

    Args:
        db: SQLAlchemy Session。
        admin: 执行操作的管理员。
        target_user_id: 待解封的用户 ID。

    Raises:
        BusinessError: 目标用户不存在或管理员权限不足时抛出。
    """
    if admin.id == target_user_id:
        raise BusinessError("Cannot perform this action on yourself", 403)

    user = get_user_by_id(db, target_user_id)
    if not user or user.is_deleted:
        raise BusinessError("User not found", 404)

    if user.role == UserRole.SUPER_ADMIN and admin.role != UserRole.SUPER_ADMIN:
        raise BusinessError("Cannot unban super-admin user", 403)

    user.status = UserStatus.ACTIVE
    user.banned_at = None
    user.ban_duration = None

    db.commit()
    db.refresh(user)
    return user
