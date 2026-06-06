from enum import IntEnum


class UserRole(IntEnum):
    """用户角色等级。"""

    USER = 0
    VIP = 1
    ADMIN = 2
    SUPER_ADMIN = 3


class UserStatus(IntEnum):
    """用户账号状态。"""

    ACTIVE = 0
    TEMP_BAN = 1
    SUSPENDED = 2
    BANNED = 3
