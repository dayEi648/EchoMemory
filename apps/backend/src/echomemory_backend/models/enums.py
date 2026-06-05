from enum import IntEnum


class UserRole(IntEnum):
    """User role levels."""

    USER = 0
    VIP = 1
    ADMIN = 2
    SUPER_ADMIN = 3


class UserStatus(IntEnum):
    """User account status."""

    ACTIVE = 0
    TEMP_BAN = 1
    SUSPENDED = 2
    BANNED = 3
