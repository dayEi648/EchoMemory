"""统一业务错误码与 HTTP 状态码常量。

本模块定义全站唯一的 ``HttpStatus`` 常量与 ``ErrorCode`` 枚举。
错误码空间按以下规则分层：

- ``0``: 成功
- ``1xxxx``: 业务规则错误（Business）
- ``2xxxx``: 认证 / 授权错误（Auth）
- ``3xxxx``: 外部 / 第三方服务错误（External）
- ``4xxxx``: 客户端请求 / 校验错误（Client）
- ``5xxxx``: 系统内部错误（System）
- ``9xxxx``: 未知 / 兜底错误

新增错误码时，应选择对应的分层区间，并尽量给出稳定的数值与明确的中文说明。
"""

from enum import IntEnum


class HttpStatus:
    """常用 HTTP 状态码常量。

    后端所有位置应优先使用这些命名常量，避免直接使用魔法数字。
    """

    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


_ERROR_CODE_HTTP_STATUS: dict["ErrorCode", int] = {}
_ERROR_CODE_DESCRIPTION: dict["ErrorCode", str] = {}


def _register(code: int, http_status: int, description: str) -> int:
    """注册错误码的元数据并返回原始整数值，供枚举成员使用。"""
    # 在枚举类创建时调用；此处先保存到临时字典，类创建后再绑定到每个成员。
    return code


class ErrorCode(IntEnum):
    """统一业务错误码枚举。

    每个成员除稳定的整数值外，还通过属性暴露：

    - ``http_status``: 推荐返回的 HTTP 状态码。
    - ``description``: 中文使用说明。

    Attributes:
        value: 业务错误码数值。
        http_status: 推荐 HTTP 状态码。
        description: 中文说明。
    """

    # -------------------------------------------------------------------------
    # 0: 成功
    # -------------------------------------------------------------------------
    SUCCESS = 0, HttpStatus.OK, "请求成功"

    # -------------------------------------------------------------------------
    # 1xxxx: 业务规则错误（Business）
    # -------------------------------------------------------------------------

    # 10000-10099: 用户账号
    USER_USERNAME_EXISTS = 10001, HttpStatus.CONFLICT, "用户名已被注册"
    USER_EMAIL_EXISTS = 10002, HttpStatus.CONFLICT, "邮箱已被注册"
    USER_PHONE_EXISTS = 10003, HttpStatus.CONFLICT, "手机号已被注册"
    USER_CREDENTIAL_EXISTS = 10004, HttpStatus.CONFLICT, "用户名、邮箱或手机号已被注册"
    USER_EMAIL_OR_PHONE_EXISTS = 10005, HttpStatus.CONFLICT, "邮箱或手机号已被注册"
    USER_NOT_FOUND = 10010, HttpStatus.NOT_FOUND, "用户不存在"
    CANNOT_FOLLOW_SELF = 10021, HttpStatus.BAD_REQUEST, "不能关注自己"
    ALREADY_FOLLOWING = 10022, HttpStatus.CONFLICT, "已关注该用户"
    NOT_FOLLOWING = 10023, HttpStatus.BAD_REQUEST, "未关注该用户"
    CANNOT_BLOCK_SELF = 10024, HttpStatus.BAD_REQUEST, "不能屏蔽自己"
    BLOCKED_BY_USER = 10025, HttpStatus.FORBIDDEN, "已被对方屏蔽"

    # 10100-10199: 音乐
    MUSIC_NOT_FOUND = 10100, HttpStatus.NOT_FOUND, "音乐不存在或未发布"
    MUSIC_ALREADY_IN_ALBUM = 10101, HttpStatus.CONFLICT, "音乐已在专辑中"
    MUSIC_BELONGS_TO_ANOTHER_ALBUM = 10102, HttpStatus.CONFLICT, "音乐已属于其他专辑"
    MUSIC_ALREADY_IN_PLAYLIST = 10103, HttpStatus.CONFLICT, "音乐已在歌单中"
    MUSIC_NOT_IN_PLAYLIST = 10104, HttpStatus.BAD_REQUEST, "歌曲不在该歌单中"
    MUSIC_NOT_IN_USER_PLAYLISTS = 10105, HttpStatus.NOT_FOUND, "歌曲不在用户任一歌单中"
    LYRICS_NOT_FOUND = 10110, HttpStatus.NOT_FOUND, "歌词不存在"

    # 10200-10299: 专辑
    ALBUM_NOT_FOUND = 10200, HttpStatus.NOT_FOUND, "专辑不存在或已删除"
    ALBUM_AUTHOR_NOT_FOUND = 10201, HttpStatus.NOT_FOUND, "专辑作者不存在或已删除"

    # 10300-10399: 歌单
    PLAYLIST_NOT_FOUND = 10300, HttpStatus.NOT_FOUND, "歌单不存在"
    PLAYLIST_SYSTEM_NOT_DELETABLE = 10303, HttpStatus.FORBIDDEN, "系统歌单不可删除"
    CANNOT_COLLECT_OWN_PLAYLIST = 10310, HttpStatus.FORBIDDEN, "不能收藏自己的歌单"

    # 10400-10499: 评论
    COMMENT_NOT_FOUND = 10400, HttpStatus.NOT_FOUND, "评论不存在"
    COMMENT_TARGET_NOT_FOUND = 10401, HttpStatus.NOT_FOUND, "评论目标不存在或不可见"
    COMMENT_PARENT_NOT_FOUND = 10402, HttpStatus.NOT_FOUND, "父评论不存在"
    COMMENT_PARENT_TARGET_MISMATCH = 10403, HttpStatus.BAD_REQUEST, "父评论与目标不匹配"

    # 10500-10599: 空间动态
    SPACE_POST_NOT_FOUND = 10500, HttpStatus.NOT_FOUND, "空间动态不存在或不可见"
    SPACE_POST_SOURCE_NOT_FOUND = 10501, HttpStatus.NOT_FOUND, "转发源不存在或不可访问"

    # 10600-10699: 字典
    DICTIONARY_TYPE_INVALID = 10600, HttpStatus.BAD_REQUEST, "字典类型无效"
    DICTIONARY_ITEM_NOT_FOUND = 10601, HttpStatus.NOT_FOUND, "字典项不存在"
    DICTIONARY_NAME_EXISTS = 10602, HttpStatus.CONFLICT, "该字典类型下名称已存在"
    DICTIONARY_ITEM_REFERENCED = 10603, HttpStatus.CONFLICT, "字典项已被其他资源引用，无法删除"

    # 10700-10799: 通知
    NOTIFICATION_NOT_FOUND = 10700, HttpStatus.NOT_FOUND, "通知不存在或不属于当前用户"

    # 10800-10899: 私信
    MESSAGE_CANNOT_WITH_SELF = 10800, HttpStatus.BAD_REQUEST, "不能与自己建立会话"
    MESSAGE_CANNOT_TO_SELF = 10801, HttpStatus.BAD_REQUEST, "不能给自己发送私信"
    MESSAGE_CONVERSATION_NOT_FOUND = 10802, HttpStatus.NOT_FOUND, "私信会话不存在"
    MESSAGE_RECIPIENT_NOT_FOUND = 10803, HttpStatus.NOT_FOUND, "收件人不存在"

    # 10900-10999: AI 对话
    AI_CONVERSATION_NOT_FOUND = 10900, HttpStatus.NOT_FOUND, "AI 对话不存在"
    AI_CONVERSATION_PERMISSION_DENIED = 10901, HttpStatus.FORBIDDEN, "无权访问该 AI 对话"

    # 10950-10999: 管理员
    ADMIN_CANNOT_MANAGE_USER = 10950, HttpStatus.FORBIDDEN, "无权操作该用户"
    ADMIN_CANNOT_CREATE_ROLE = 10951, HttpStatus.FORBIDDEN, "无权创建该角色的用户"
    ADMIN_CANNOT_PROMOTE_SUPER_ADMIN = 10952, HttpStatus.FORBIDDEN, "不能将用户提升为超级管理员"
    ADMIN_USER_STATE_INVALID = 10953, HttpStatus.BAD_REQUEST, "用户状态组合无效"
    ADMIN_BAN_STATE_INVALID = 10954, HttpStatus.BAD_REQUEST, "封禁状态或时长无效"

    # 11000-11099: 播放历史
    PLAY_HISTORY_NOT_FOUND = 11000, HttpStatus.NOT_FOUND, "播放历史记录不存在"

    # 11100-11199: 轮播图
    CAROUSEL_ITEM_NOT_FOUND = 11100, HttpStatus.NOT_FOUND, "轮播图不存在"

    # 11200-11299: 音乐知识库
    MUSIC_KNOWLEDGE_SOURCE_NOT_FOUND = 11200, HttpStatus.NOT_FOUND, "音乐知识库文档不存在"

    # -------------------------------------------------------------------------
    # 2xxxx: 认证 / 授权错误（Auth）
    # -------------------------------------------------------------------------
    AUTH_CREDENTIALS_INVALID = 20001, HttpStatus.UNAUTHORIZED, "用户名或密码错误"
    AUTH_ACCOUNT_DELETED = 20002, HttpStatus.UNAUTHORIZED, "账号已被删除"
    AUTH_ACCOUNT_BANNED = 20003, HttpStatus.FORBIDDEN, "账号已被封禁"
    AUTH_REFRESH_TOKEN_INVALID = 20010, HttpStatus.UNAUTHORIZED, "刷新令牌无效或已过期"
    AUTH_TOKEN_REVOKED = 20011, HttpStatus.UNAUTHORIZED, "令牌已被吊销"
    AUTH_USER_NOT_FOUND = 20012, HttpStatus.UNAUTHORIZED, "认证用户不存在"
    AUTH_ACCOUNT_INACTIVE = 20020, HttpStatus.FORBIDDEN, "用户账号未激活"
    PERMISSION_DENIED = 20100, HttpStatus.FORBIDDEN, "权限不足"

    # -------------------------------------------------------------------------
    # 3xxxx: 外部 / 第三方服务错误（External）
    # -------------------------------------------------------------------------
    EXTERNAL_AI_RESPONSE_FAILED = 30001, HttpStatus.INTERNAL_SERVER_ERROR, "AI 服务响应失败"
    EXTERNAL_LYRICS_LOAD_FAILED = 30002, HttpStatus.BAD_GATEWAY, "歌词文件加载失败"
    EXTERNAL_FILE_UPLOAD_FAILED = 30003, HttpStatus.SERVICE_UNAVAILABLE, "文件上传失败"

    # -------------------------------------------------------------------------
    # 4xxxx: 客户端请求 / 校验错误（Client）
    # -------------------------------------------------------------------------
    CLIENT_INVALID_AUTHOR_ID = 40001, HttpStatus.BAD_REQUEST, "作者 ID 无效"
    CLIENT_INVALID_INSTRUMENT_ID = 40002, HttpStatus.BAD_REQUEST, "乐器 ID 无效"
    CLIENT_INVALID_EMOTION_TAG_ID = 40003, HttpStatus.BAD_REQUEST, "情绪标签 ID 无效"
    CLIENT_INVALID_INTEREST_TAG_ID = 40004, HttpStatus.BAD_REQUEST, "兴趣标签 ID 无效"
    CLIENT_INVALID_REFERENCE_IN_ALBUM = 40005, HttpStatus.BAD_REQUEST, "专辑数据中存在无效引用"
    CLIENT_INVALID_REFERENCE_IN_MUSIC = 40006, HttpStatus.BAD_REQUEST, "音乐数据中存在无效引用"
    CLIENT_INVALID_TARGET_TYPE = 40007, HttpStatus.BAD_REQUEST, "目标类型无效"
    CLIENT_INVALID_SOURCE_TYPE = 40008, HttpStatus.BAD_REQUEST, "转发源类型无效"
    CLIENT_INVALID_RELEASE_DATE = 40011, HttpStatus.UNPROCESSABLE_ENTITY, "发行日期格式必须为 YYYY-MM-DD"
    CLIENT_INVALID_RELEASE_DATE_FROM = 40012, HttpStatus.UNPROCESSABLE_ENTITY, "发行日期起始格式必须为 YYYY-MM-DD"
    CLIENT_INVALID_RELEASE_DATE_TO = 40013, HttpStatus.UNPROCESSABLE_ENTITY, "发行日期截止格式必须为 YYYY-MM-DD"
    CLIENT_NAME_REQUIRED = 40021, HttpStatus.UNPROCESSABLE_ENTITY, "更新字典项必须提供名称"
    CLIENT_COVER_FILE_REQUIRED = 40022, HttpStatus.UNPROCESSABLE_ENTITY, "至少需提供一张封面文件"
    CLIENT_CONTENT_OR_FILE_REQUIRED = 40023, HttpStatus.UNPROCESSABLE_ENTITY, "动态内容或至少一个文件必填"
    CLIENT_AUDIO_FILE_TYPE_INVALID = 40031, HttpStatus.UNPROCESSABLE_ENTITY, "音频文件类型无效"
    CLIENT_FILE_MUST_BE_IMAGE = 40032, HttpStatus.UNPROCESSABLE_ENTITY, "上传文件必须是图片"
    CLIENT_INVALID_IMAGE_FILE = 40033, HttpStatus.UNPROCESSABLE_ENTITY, "图片文件无效"
    CLIENT_CAROUSEL_REORDER_MISMATCH = 40041, HttpStatus.UNPROCESSABLE_ENTITY, "轮播图 ID 列表与实际数量不匹配"
    CLIENT_MUSIC_KNOWLEDGE_UNSUPPORTED_FILE_TYPE = 40042, HttpStatus.UNPROCESSABLE_ENTITY, "音乐知识库不支持该文件类型"
    CLIENT_INVALID_REQUEST_PARAMETERS = 40050, HttpStatus.UNPROCESSABLE_ENTITY, "请求参数校验失败"
    CLIENT_RATE_LIMIT_UPLOAD = 42901, HttpStatus.TOO_MANY_REQUESTS, "上传请求过于频繁，请稍后再试"
    CLIENT_RATE_LIMIT_LOGIN = 42902, HttpStatus.TOO_MANY_REQUESTS, "登录尝试过于频繁，请稍后再试"

    # -------------------------------------------------------------------------
    # 5xxxx: 系统内部错误（System）
    # -------------------------------------------------------------------------
    SYSTEM_INTERNAL_ERROR = 50001, HttpStatus.INTERNAL_SERVER_ERROR, "系统内部错误"
    SYSTEM_CONVERSATION_CREATE_FAILED = 50002, HttpStatus.INTERNAL_SERVER_ERROR, "系统创建会话失败"
    SYSTEM_MUSIC_KNOWLEDGE_INGEST_FAILED = 50003, HttpStatus.INTERNAL_SERVER_ERROR, "音乐知识库文档入库失败"

    # -------------------------------------------------------------------------
    # 9xxxx: 未知 / 兜底错误（Unknown）
    # -------------------------------------------------------------------------
    UNKNOWN_ERROR = 90001, HttpStatus.INTERNAL_SERVER_ERROR, "未知错误"
    RESOURCE_NOT_FOUND = 90002, HttpStatus.NOT_FOUND, "资源不存在"

    def __new__(cls, value: int, http_status: int, description: str) -> "ErrorCode":
        obj = int.__new__(cls, value)
        obj._value_ = value
        _ERROR_CODE_HTTP_STATUS[obj] = http_status
        _ERROR_CODE_DESCRIPTION[obj] = description
        return obj

    @property
    def http_status(self) -> int:
        """返回该错误码推荐的 HTTP 状态码。"""
        return _ERROR_CODE_HTTP_STATUS[self]

    @property
    def description(self) -> str:
        """返回该错误码的中文说明。"""
        return _ERROR_CODE_DESCRIPTION[self]

    @classmethod
    def from_status(cls, status_code: int) -> "ErrorCode":
        """根据 HTTP 状态码返回一个通用的错误码。

        用于 ``HTTPException`` 等未携带业务错误码的场景兜底。
        """
        mapping = {
            HttpStatus.BAD_REQUEST: cls.CLIENT_INVALID_REQUEST_PARAMETERS,
            HttpStatus.UNAUTHORIZED: cls.AUTH_CREDENTIALS_INVALID,
            HttpStatus.FORBIDDEN: cls.PERMISSION_DENIED,
            HttpStatus.NOT_FOUND: cls.RESOURCE_NOT_FOUND,
            HttpStatus.CONFLICT: cls.USER_CREDENTIAL_EXISTS,
            HttpStatus.UNPROCESSABLE_ENTITY: cls.CLIENT_INVALID_REQUEST_PARAMETERS,
            HttpStatus.TOO_MANY_REQUESTS: cls.CLIENT_RATE_LIMIT_LOGIN,
            HttpStatus.INTERNAL_SERVER_ERROR: cls.SYSTEM_INTERNAL_ERROR,
            HttpStatus.BAD_GATEWAY: cls.EXTERNAL_LYRICS_LOAD_FAILED,
            HttpStatus.SERVICE_UNAVAILABLE: cls.EXTERNAL_FILE_UPLOAD_FAILED,
        }
        return mapping.get(status_code, cls.UNKNOWN_ERROR)
