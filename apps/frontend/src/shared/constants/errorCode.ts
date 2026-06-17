/** 统一业务错误码枚举。
 *
 * 与后端 `echomemory_backend.core.exceptions.codes.ErrorCode` 保持数值一致。
 * 错误码空间分层：
 *   0      : 成功
 *   1xxxx  : 业务规则错误（Business）
 *   2xxxx  : 认证 / 授权错误（Auth）
 *   3xxxx  : 外部 / 第三方服务错误（External）
 *   4xxxx  : 客户端请求 / 校验错误（Client）
 *   5xxxx  : 系统内部错误（System）
 *   9xxxx  : 未知 / 兜底错误（Unknown）
 */
export enum ErrorCode {
  // 0: 成功
  SUCCESS = 0,

  // 1xxxx: 业务规则错误（Business）
  // 10000-10099: 用户账号
  USER_USERNAME_EXISTS = 10001,
  USER_EMAIL_EXISTS = 10002,
  USER_PHONE_EXISTS = 10003,
  USER_CREDENTIAL_EXISTS = 10004,
  USER_EMAIL_OR_PHONE_EXISTS = 10005,
  USER_NOT_FOUND = 10010,
  CANNOT_FOLLOW_SELF = 10021,
  ALREADY_FOLLOWING = 10022,
  NOT_FOLLOWING = 10023,
  CANNOT_BLOCK_SELF = 10024,
  BLOCKED_BY_USER = 10025,

  // 10100-10199: 音乐
  MUSIC_NOT_FOUND = 10100,
  MUSIC_ALREADY_IN_ALBUM = 10101,
  MUSIC_BELONGS_TO_ANOTHER_ALBUM = 10102,
  MUSIC_ALREADY_IN_PLAYLIST = 10103,
  MUSIC_NOT_IN_PLAYLIST = 10104,
  MUSIC_NOT_IN_USER_PLAYLISTS = 10105,
  LYRICS_NOT_FOUND = 10110,

  // 10200-10299: 专辑
  ALBUM_NOT_FOUND = 10200,
  ALBUM_AUTHOR_NOT_FOUND = 10201,

  // 10300-10399: 歌单
  PLAYLIST_NOT_FOUND = 10300,
  PLAYLIST_SYSTEM_NOT_DELETABLE = 10303,
  CANNOT_COLLECT_OWN_PLAYLIST = 10310,

  // 10400-10499: 评论
  COMMENT_NOT_FOUND = 10400,
  COMMENT_TARGET_NOT_FOUND = 10401,
  COMMENT_PARENT_NOT_FOUND = 10402,
  COMMENT_PARENT_TARGET_MISMATCH = 10403,

  // 10500-10599: 空间动态
  SPACE_POST_NOT_FOUND = 10500,
  SPACE_POST_SOURCE_NOT_FOUND = 10501,

  // 10600-10699: 字典
  DICTIONARY_TYPE_INVALID = 10600,
  DICTIONARY_ITEM_NOT_FOUND = 10601,
  DICTIONARY_NAME_EXISTS = 10602,
  DICTIONARY_ITEM_REFERENCED = 10603,

  // 10700-10799: 通知
  NOTIFICATION_NOT_FOUND = 10700,
  NOTIFICATION_TARGET_TYPE_INVALID = 10701,

  // 10800-10899: 私信
  MESSAGE_CANNOT_WITH_SELF = 10800,
  MESSAGE_CANNOT_TO_SELF = 10801,
  MESSAGE_CONVERSATION_NOT_FOUND = 10802,
  MESSAGE_RECIPIENT_NOT_FOUND = 10803,

  // 10900-10999: AI 对话
  AI_CONVERSATION_NOT_FOUND = 10900,
  AI_CONVERSATION_PERMISSION_DENIED = 10901,

  // 10950-10999: 管理员
  ADMIN_CANNOT_MANAGE_USER = 10950,
  ADMIN_CANNOT_CREATE_ROLE = 10951,
  ADMIN_CANNOT_PROMOTE_SUPER_ADMIN = 10952,
  ADMIN_USER_STATE_INVALID = 10953,
  ADMIN_BAN_STATE_INVALID = 10954,

  // 11000-11099: 播放历史
  PLAY_HISTORY_NOT_FOUND = 11000,

  // 11100-11199: 轮播图
  CAROUSEL_ITEM_NOT_FOUND = 11100,

  // 2xxxx: 认证 / 授权错误（Auth）
  AUTH_CREDENTIALS_INVALID = 20001,
  AUTH_ACCOUNT_DELETED = 20002,
  AUTH_ACCOUNT_BANNED = 20003,
  AUTH_REFRESH_TOKEN_INVALID = 20010,
  AUTH_TOKEN_REVOKED = 20011,
  AUTH_USER_NOT_FOUND = 20012,
  AUTH_ACCOUNT_INACTIVE = 20020,
  PERMISSION_DENIED = 20100,
  ADMIN_PRIVILEGE_REQUIRED = 20101,

  // 3xxxx: 外部 / 第三方服务错误（External）
  EXTERNAL_AI_RESPONSE_FAILED = 30001,
  EXTERNAL_LYRICS_LOAD_FAILED = 30002,
  EXTERNAL_FILE_UPLOAD_FAILED = 30003,

  // 4xxxx: 客户端请求 / 校验错误（Client）
  CLIENT_INVALID_AUTHOR_ID = 40001,
  CLIENT_INVALID_INSTRUMENT_ID = 40002,
  CLIENT_INVALID_EMOTION_TAG_ID = 40003,
  CLIENT_INVALID_INTEREST_TAG_ID = 40004,
  CLIENT_INVALID_REFERENCE_IN_ALBUM = 40005,
  CLIENT_INVALID_REFERENCE_IN_MUSIC = 40006,
  CLIENT_INVALID_TARGET_TYPE = 40007,
  CLIENT_INVALID_SOURCE_TYPE = 40008,
  CLIENT_INVALID_RELEASE_DATE = 40011,
  CLIENT_INVALID_RELEASE_DATE_FROM = 40012,
  CLIENT_INVALID_RELEASE_DATE_TO = 40013,
  CLIENT_NAME_REQUIRED = 40021,
  CLIENT_COVER_FILE_REQUIRED = 40022,
  CLIENT_CONTENT_OR_FILE_REQUIRED = 40023,
  CLIENT_AUDIO_FILE_TYPE_INVALID = 40031,
  CLIENT_FILE_MUST_BE_IMAGE = 40032,
  CLIENT_INVALID_IMAGE_FILE = 40033,
  CLIENT_CAROUSEL_REORDER_MISMATCH = 40041,
  CLIENT_INVALID_REQUEST_PARAMETERS = 40050,
  CLIENT_RATE_LIMIT_UPLOAD = 42901,
  CLIENT_RATE_LIMIT_LOGIN = 42902,

  // 5xxxx: 系统内部错误（System）
  SYSTEM_INTERNAL_ERROR = 50001,
  SYSTEM_CONVERSATION_CREATE_FAILED = 50002,

  // 9xxxx: 未知 / 兜底错误（Unknown）
  UNKNOWN_ERROR = 90001,
  RESOURCE_NOT_FOUND = 90002,
}

/** 错误码分层标签。 */
export type ErrorCodeLayer =
  | "success"
  | "business"
  | "auth"
  | "external"
  | "client"
  | "system"
  | "unknown";

/** 获取错误码所属分层。 */
export function getErrorCodeLayer(code: ErrorCode | number): ErrorCodeLayer {
  const value = Number(code);
  if (value === 0) return "success";
  if (value >= 10000 && value < 20000) return "business";
  if (value >= 20000 && value < 30000) return "auth";
  if (value >= 30000 && value < 40000) return "external";
  if (value >= 40000 && value < 50000) return "client";
  if (value >= 50000 && value < 60000) return "system";
  return "unknown";
}

/** 错误码 → 中文说明映射（与后端 ErrorCode.description 同步）。 */
const ERROR_CODE_DESCRIPTIONS: Record<number, string> = {
  [ErrorCode.SUCCESS]: "请求成功",
  [ErrorCode.USER_USERNAME_EXISTS]: "用户名已被注册",
  [ErrorCode.USER_EMAIL_EXISTS]: "邮箱已被注册",
  [ErrorCode.USER_PHONE_EXISTS]: "手机号已被注册",
  [ErrorCode.USER_CREDENTIAL_EXISTS]: "用户名、邮箱或手机号已被注册",
  [ErrorCode.USER_EMAIL_OR_PHONE_EXISTS]: "邮箱或手机号已被注册",
  [ErrorCode.USER_NOT_FOUND]: "用户不存在",
  [ErrorCode.CANNOT_FOLLOW_SELF]: "不能关注自己",
  [ErrorCode.ALREADY_FOLLOWING]: "已关注该用户",
  [ErrorCode.NOT_FOLLOWING]: "未关注该用户",
  [ErrorCode.CANNOT_BLOCK_SELF]: "不能屏蔽自己",
  [ErrorCode.BLOCKED_BY_USER]: "已被对方屏蔽",
  [ErrorCode.MUSIC_NOT_FOUND]: "音乐不存在或未发布",
  [ErrorCode.MUSIC_ALREADY_IN_ALBUM]: "音乐已在专辑中",
  [ErrorCode.MUSIC_BELONGS_TO_ANOTHER_ALBUM]: "音乐已属于其他专辑",
  [ErrorCode.MUSIC_ALREADY_IN_PLAYLIST]: "音乐已在歌单中",
  [ErrorCode.MUSIC_NOT_IN_PLAYLIST]: "歌曲不在该歌单中",
  [ErrorCode.MUSIC_NOT_IN_USER_PLAYLISTS]: "歌曲不在用户任一歌单中",
  [ErrorCode.LYRICS_NOT_FOUND]: "歌词不存在",
  [ErrorCode.ALBUM_NOT_FOUND]: "专辑不存在或已删除",
  [ErrorCode.ALBUM_AUTHOR_NOT_FOUND]: "专辑作者不存在或已删除",
  [ErrorCode.PLAYLIST_NOT_FOUND]: "歌单不存在",
  [ErrorCode.PLAYLIST_SYSTEM_NOT_DELETABLE]: "系统歌单不可删除",
  [ErrorCode.CANNOT_COLLECT_OWN_PLAYLIST]: "不能收藏自己的歌单",
  [ErrorCode.COMMENT_NOT_FOUND]: "评论不存在",
  [ErrorCode.COMMENT_TARGET_NOT_FOUND]: "评论目标不存在或不可见",
  [ErrorCode.COMMENT_PARENT_NOT_FOUND]: "父评论不存在",
  [ErrorCode.COMMENT_PARENT_TARGET_MISMATCH]: "父评论与目标不匹配",
  [ErrorCode.SPACE_POST_NOT_FOUND]: "空间动态不存在或不可见",
  [ErrorCode.SPACE_POST_SOURCE_NOT_FOUND]: "转发源不存在或不可访问",
  [ErrorCode.DICTIONARY_TYPE_INVALID]: "字典类型无效",
  [ErrorCode.DICTIONARY_ITEM_NOT_FOUND]: "字典项不存在",
  [ErrorCode.DICTIONARY_NAME_EXISTS]: "该字典类型下名称已存在",
  [ErrorCode.DICTIONARY_ITEM_REFERENCED]: "字典项已被其他资源引用，无法删除",
  [ErrorCode.NOTIFICATION_NOT_FOUND]: "通知不存在或不属于当前用户",
  [ErrorCode.NOTIFICATION_TARGET_TYPE_INVALID]: "通知目标类型无效",
  [ErrorCode.MESSAGE_CANNOT_WITH_SELF]: "不能与自己建立会话",
  [ErrorCode.MESSAGE_CANNOT_TO_SELF]: "不能给自己发送私信",
  [ErrorCode.MESSAGE_CONVERSATION_NOT_FOUND]: "私信会话不存在",
  [ErrorCode.MESSAGE_RECIPIENT_NOT_FOUND]: "收件人不存在",
  [ErrorCode.AI_CONVERSATION_NOT_FOUND]: "AI 对话不存在",
  [ErrorCode.AI_CONVERSATION_PERMISSION_DENIED]: "无权访问该 AI 对话",
  [ErrorCode.ADMIN_CANNOT_MANAGE_USER]: "无权操作该用户",
  [ErrorCode.ADMIN_CANNOT_CREATE_ROLE]: "无权创建该角色的用户",
  [ErrorCode.ADMIN_CANNOT_PROMOTE_SUPER_ADMIN]: "不能将用户提升为超级管理员",
  [ErrorCode.ADMIN_USER_STATE_INVALID]: "用户状态组合无效",
  [ErrorCode.ADMIN_BAN_STATE_INVALID]: "封禁状态或时长无效",
  [ErrorCode.PLAY_HISTORY_NOT_FOUND]: "播放历史记录不存在",
  [ErrorCode.CAROUSEL_ITEM_NOT_FOUND]: "轮播图不存在",
  [ErrorCode.AUTH_CREDENTIALS_INVALID]: "用户名或密码错误",
  [ErrorCode.AUTH_ACCOUNT_DELETED]: "账号已被删除",
  [ErrorCode.AUTH_ACCOUNT_BANNED]: "账号已被封禁",
  [ErrorCode.AUTH_REFRESH_TOKEN_INVALID]: "刷新令牌无效或已过期",
  [ErrorCode.AUTH_TOKEN_REVOKED]: "令牌已被吊销",
  [ErrorCode.AUTH_USER_NOT_FOUND]: "认证用户不存在",
  [ErrorCode.AUTH_ACCOUNT_INACTIVE]: "用户账号未激活",
  [ErrorCode.PERMISSION_DENIED]: "权限不足",
  [ErrorCode.ADMIN_PRIVILEGE_REQUIRED]: "需要管理员权限",
  [ErrorCode.EXTERNAL_AI_RESPONSE_FAILED]: "AI 服务响应失败",
  [ErrorCode.EXTERNAL_LYRICS_LOAD_FAILED]: "歌词文件加载失败",
  [ErrorCode.EXTERNAL_FILE_UPLOAD_FAILED]: "文件上传失败",
  [ErrorCode.CLIENT_INVALID_AUTHOR_ID]: "作者 ID 无效",
  [ErrorCode.CLIENT_INVALID_INSTRUMENT_ID]: "乐器 ID 无效",
  [ErrorCode.CLIENT_INVALID_EMOTION_TAG_ID]: "情绪标签 ID 无效",
  [ErrorCode.CLIENT_INVALID_INTEREST_TAG_ID]: "兴趣标签 ID 无效",
  [ErrorCode.CLIENT_INVALID_REFERENCE_IN_ALBUM]: "专辑数据中存在无效引用",
  [ErrorCode.CLIENT_INVALID_REFERENCE_IN_MUSIC]: "音乐数据中存在无效引用",
  [ErrorCode.CLIENT_INVALID_TARGET_TYPE]: "目标类型无效",
  [ErrorCode.CLIENT_INVALID_SOURCE_TYPE]: "转发源类型无效",
  [ErrorCode.CLIENT_INVALID_RELEASE_DATE]: "发行日期格式必须为 YYYY-MM-DD",
  [ErrorCode.CLIENT_INVALID_RELEASE_DATE_FROM]: "发行日期起始格式必须为 YYYY-MM-DD",
  [ErrorCode.CLIENT_INVALID_RELEASE_DATE_TO]: "发行日期截止格式必须为 YYYY-MM-DD",
  [ErrorCode.CLIENT_NAME_REQUIRED]: "更新字典项必须提供名称",
  [ErrorCode.CLIENT_COVER_FILE_REQUIRED]: "至少需提供一张封面文件",
  [ErrorCode.CLIENT_CONTENT_OR_FILE_REQUIRED]: "动态内容或至少一个文件必填",
  [ErrorCode.CLIENT_AUDIO_FILE_TYPE_INVALID]: "音频文件类型无效",
  [ErrorCode.CLIENT_FILE_MUST_BE_IMAGE]: "上传文件必须是图片",
  [ErrorCode.CLIENT_INVALID_IMAGE_FILE]: "图片文件无效",
  [ErrorCode.CLIENT_CAROUSEL_REORDER_MISMATCH]: "轮播图 ID 列表与实际数量不匹配",
  [ErrorCode.CLIENT_INVALID_REQUEST_PARAMETERS]: "请求参数校验失败",
  [ErrorCode.CLIENT_RATE_LIMIT_UPLOAD]: "上传请求过于频繁，请稍后再试",
  [ErrorCode.CLIENT_RATE_LIMIT_LOGIN]: "登录尝试过于频繁，请稍后再试",
  [ErrorCode.SYSTEM_INTERNAL_ERROR]: "系统内部错误",
  [ErrorCode.SYSTEM_CONVERSATION_CREATE_FAILED]: "系统创建会话失败",
  [ErrorCode.UNKNOWN_ERROR]: "未知错误",
  [ErrorCode.RESOURCE_NOT_FOUND]: "资源不存在",
};

/** 获取错误码的简短中文说明（兜底）。 */
export function getErrorCodeDescription(code: ErrorCode | number): string {
  return ERROR_CODE_DESCRIPTIONS[Number(code)] ?? "请求失败";
}
