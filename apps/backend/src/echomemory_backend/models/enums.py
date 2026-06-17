"""定义项目中使用的枚举类型。"""

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
    MUTED = 1
    RESTRICTED = 2
    BANNED = 3


class NotificationType(IntEnum):
    """通知类型枚举。"""

    FOLLOW = 0
    COMMENT_REPLY = 1
    COMMENT_LIKE = 2
    SPACE_POST_LIKE = 3
    SPACE_POST_COMMENT = 4
