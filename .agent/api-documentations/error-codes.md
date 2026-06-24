# echomemory 错误码与 HTTP 状态码规范

> 本文档由 `apps/backend/scripts/generate_error_code_doc.py` 自动生成，请勿手动修改。新增或变更错误码后，请重新运行该脚本。

## HTTP 状态码语义

| 状态码 | 常量名 | 使用场景 |
| ---: | --- | --- |
| 200 | `OK` | 请求成功，返回业务数据 |
| 201 | `CREATED` | 资源创建成功 |
| 204 | `NO_CONTENT` | 操作成功但无返回体；中间件会转换为 200 + data=null |
| 400 | `BAD_REQUEST` | 请求语法或语义错误，无法被服务端理解 |
| 401 | `UNAUTHORIZED` | 未认证或认证凭据无效 |
| 403 | `FORBIDDEN` | 已认证但无权访问该资源 |
| 404 | `NOT_FOUND` | 请求的资源不存在 |
| 409 | `CONFLICT` | 业务冲突，如重复注册 |
| 422 | `UNPROCESSABLE_ENTITY` | 请求参数校验失败 |
| 429 | `TOO_MANY_REQUESTS` | 请求过于频繁，触发限流 |
| 500 | `INTERNAL_SERVER_ERROR` | 系统内部未捕获异常 |
| 502 | `BAD_GATEWAY` | 网关或上游服务异常 |
| 503 | `SERVICE_UNAVAILABLE` | 服务暂时不可用 |

## 错误码空间分层

| 区间 | 分层 | 说明 |
| --- | --- | --- |
| 0 | 成功 | 请求成功 |
| 10000 - 19999 | 业务规则错误 | 用户、音乐、专辑、歌单、评论等业务规则被违反 |
| 20000 - 29999 | 认证 / 授权错误 | 登录、Token、权限相关 |
| 30000 - 39999 | 外部 / 第三方服务错误 | AI、OSS、歌词加载等外部依赖 |
| 40000 - 49999 | 客户端请求 / 校验错误 | 参数校验、格式错误、限流 |
| 50000 - 59999 | 系统内部错误 | 未捕获异常、系统级失败 |
| 90000 - 99999 | 未知 / 兜底错误 | 未明确分类的兜底错误 |

## 成功 {#成功}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 0 | `SUCCESS` | 200 | 请求成功 |

## 业务规则错误 {#业务规则错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 10001 | `USER_USERNAME_EXISTS` | 409 | 用户名已被注册 |
| 10002 | `USER_EMAIL_EXISTS` | 409 | 邮箱已被注册 |
| 10003 | `USER_PHONE_EXISTS` | 409 | 手机号已被注册 |
| 10004 | `USER_CREDENTIAL_EXISTS` | 409 | 用户名、邮箱或手机号已被注册 |
| 10005 | `USER_EMAIL_OR_PHONE_EXISTS` | 409 | 邮箱或手机号已被注册 |
| 10010 | `USER_NOT_FOUND` | 404 | 用户不存在 |
| 10021 | `CANNOT_FOLLOW_SELF` | 400 | 不能关注自己 |
| 10022 | `ALREADY_FOLLOWING` | 409 | 已关注该用户 |
| 10023 | `NOT_FOLLOWING` | 400 | 未关注该用户 |
| 10024 | `CANNOT_BLOCK_SELF` | 400 | 不能屏蔽自己 |
| 10025 | `BLOCKED_BY_USER` | 403 | 已被对方屏蔽 |
| 10100 | `MUSIC_NOT_FOUND` | 404 | 音乐不存在或未发布 |
| 10101 | `MUSIC_ALREADY_IN_ALBUM` | 409 | 音乐已在专辑中 |
| 10102 | `MUSIC_BELONGS_TO_ANOTHER_ALBUM` | 409 | 音乐已属于其他专辑 |
| 10103 | `MUSIC_ALREADY_IN_PLAYLIST` | 409 | 音乐已在歌单中 |
| 10104 | `MUSIC_NOT_IN_PLAYLIST` | 400 | 歌曲不在该歌单中 |
| 10105 | `MUSIC_NOT_IN_USER_PLAYLISTS` | 404 | 歌曲不在用户任一歌单中 |
| 10110 | `LYRICS_NOT_FOUND` | 404 | 歌词不存在 |
| 10200 | `ALBUM_NOT_FOUND` | 404 | 专辑不存在或已删除 |
| 10201 | `ALBUM_AUTHOR_NOT_FOUND` | 404 | 专辑作者不存在或已删除 |
| 10300 | `PLAYLIST_NOT_FOUND` | 404 | 歌单不存在 |
| 10303 | `PLAYLIST_SYSTEM_NOT_DELETABLE` | 403 | 系统歌单不可删除 |
| 10310 | `CANNOT_COLLECT_OWN_PLAYLIST` | 403 | 不能收藏自己的歌单 |
| 10400 | `COMMENT_NOT_FOUND` | 404 | 评论不存在 |
| 10401 | `COMMENT_TARGET_NOT_FOUND` | 404 | 评论目标不存在或不可见 |
| 10402 | `COMMENT_PARENT_NOT_FOUND` | 404 | 父评论不存在 |
| 10403 | `COMMENT_PARENT_TARGET_MISMATCH` | 400 | 父评论与目标不匹配 |
| 10500 | `SPACE_POST_NOT_FOUND` | 404 | 空间动态不存在或不可见 |
| 10501 | `SPACE_POST_SOURCE_NOT_FOUND` | 404 | 转发源不存在或不可访问 |
| 10600 | `DICTIONARY_TYPE_INVALID` | 400 | 字典类型无效 |
| 10601 | `DICTIONARY_ITEM_NOT_FOUND` | 404 | 字典项不存在 |
| 10602 | `DICTIONARY_NAME_EXISTS` | 409 | 该字典类型下名称已存在 |
| 10603 | `DICTIONARY_ITEM_REFERENCED` | 409 | 字典项已被其他资源引用，无法删除 |
| 10700 | `NOTIFICATION_NOT_FOUND` | 404 | 通知不存在或不属于当前用户 |
| 10701 | `NOTIFICATION_TARGET_TYPE_INVALID` | 400 | 通知目标类型无效 |
| 10800 | `MESSAGE_CANNOT_WITH_SELF` | 400 | 不能与自己建立会话 |
| 10801 | `MESSAGE_CANNOT_TO_SELF` | 400 | 不能给自己发送私信 |
| 10802 | `MESSAGE_CONVERSATION_NOT_FOUND` | 404 | 私信会话不存在 |
| 10803 | `MESSAGE_RECIPIENT_NOT_FOUND` | 404 | 收件人不存在 |
| 10900 | `AI_CONVERSATION_NOT_FOUND` | 404 | AI 对话不存在 |
| 10901 | `AI_CONVERSATION_PERMISSION_DENIED` | 403 | 无权访问该 AI 对话 |
| 10950 | `ADMIN_CANNOT_MANAGE_USER` | 403 | 无权操作该用户 |
| 10951 | `ADMIN_CANNOT_CREATE_ROLE` | 403 | 无权创建该角色的用户 |
| 10952 | `ADMIN_CANNOT_PROMOTE_SUPER_ADMIN` | 403 | 不能将用户提升为超级管理员 |
| 10953 | `ADMIN_USER_STATE_INVALID` | 400 | 用户状态组合无效 |
| 10954 | `ADMIN_BAN_STATE_INVALID` | 400 | 封禁状态或时长无效 |
| 11000 | `PLAY_HISTORY_NOT_FOUND` | 404 | 播放历史记录不存在 |
| 11100 | `CAROUSEL_ITEM_NOT_FOUND` | 404 | 轮播图不存在 |

## 认证 / 授权错误 {#认证-授权错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 20001 | `AUTH_CREDENTIALS_INVALID` | 401 | 用户名或密码错误 |
| 20002 | `AUTH_ACCOUNT_DELETED` | 401 | 账号已被删除 |
| 20003 | `AUTH_ACCOUNT_BANNED` | 403 | 账号已被封禁 |
| 20010 | `AUTH_REFRESH_TOKEN_INVALID` | 401 | 刷新令牌无效或已过期 |
| 20011 | `AUTH_TOKEN_REVOKED` | 401 | 令牌已被吊销 |
| 20012 | `AUTH_USER_NOT_FOUND` | 401 | 认证用户不存在 |
| 20020 | `AUTH_ACCOUNT_INACTIVE` | 403 | 用户账号未激活 |
| 20100 | `PERMISSION_DENIED` | 403 | 权限不足 |
| 20101 | `ADMIN_PRIVILEGE_REQUIRED` | 403 | 需要管理员权限 |

## 外部 / 第三方服务错误 {#外部-第三方服务错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 30001 | `EXTERNAL_AI_RESPONSE_FAILED` | 500 | AI 服务响应失败 |
| 30002 | `EXTERNAL_LYRICS_LOAD_FAILED` | 502 | 歌词文件加载失败 |
| 30003 | `EXTERNAL_FILE_UPLOAD_FAILED` | 503 | 文件上传失败 |

## 客户端请求 / 校验错误 {#客户端请求-校验错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 40001 | `CLIENT_INVALID_AUTHOR_ID` | 400 | 作者 ID 无效 |
| 40002 | `CLIENT_INVALID_INSTRUMENT_ID` | 400 | 乐器 ID 无效 |
| 40003 | `CLIENT_INVALID_EMOTION_TAG_ID` | 400 | 情绪标签 ID 无效 |
| 40004 | `CLIENT_INVALID_INTEREST_TAG_ID` | 400 | 兴趣标签 ID 无效 |
| 40005 | `CLIENT_INVALID_REFERENCE_IN_ALBUM` | 400 | 专辑数据中存在无效引用 |
| 40006 | `CLIENT_INVALID_REFERENCE_IN_MUSIC` | 400 | 音乐数据中存在无效引用 |
| 40007 | `CLIENT_INVALID_TARGET_TYPE` | 400 | 目标类型无效 |
| 40008 | `CLIENT_INVALID_SOURCE_TYPE` | 400 | 转发源类型无效 |
| 40011 | `CLIENT_INVALID_RELEASE_DATE` | 422 | 发行日期格式必须为 YYYY-MM-DD |
| 40012 | `CLIENT_INVALID_RELEASE_DATE_FROM` | 422 | 发行日期起始格式必须为 YYYY-MM-DD |
| 40013 | `CLIENT_INVALID_RELEASE_DATE_TO` | 422 | 发行日期截止格式必须为 YYYY-MM-DD |
| 40021 | `CLIENT_NAME_REQUIRED` | 422 | 更新字典项必须提供名称 |
| 40022 | `CLIENT_COVER_FILE_REQUIRED` | 422 | 至少需提供一张封面文件 |
| 40023 | `CLIENT_CONTENT_OR_FILE_REQUIRED` | 422 | 动态内容或至少一个文件必填 |
| 40031 | `CLIENT_AUDIO_FILE_TYPE_INVALID` | 422 | 音频文件类型无效 |
| 40032 | `CLIENT_FILE_MUST_BE_IMAGE` | 422 | 上传文件必须是图片 |
| 40033 | `CLIENT_INVALID_IMAGE_FILE` | 422 | 图片文件无效 |
| 40041 | `CLIENT_CAROUSEL_REORDER_MISMATCH` | 422 | 轮播图 ID 列表与实际数量不匹配 |
| 40050 | `CLIENT_INVALID_REQUEST_PARAMETERS` | 422 | 请求参数校验失败 |
| 42901 | `CLIENT_RATE_LIMIT_UPLOAD` | 429 | 上传请求过于频繁，请稍后再试 |
| 42902 | `CLIENT_RATE_LIMIT_LOGIN` | 429 | 登录尝试过于频繁，请稍后再试 |

## 系统内部错误 {#系统内部错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 50001 | `SYSTEM_INTERNAL_ERROR` | 500 | 系统内部错误 |
| 50002 | `SYSTEM_CONVERSATION_CREATE_FAILED` | 500 | 系统创建会话失败 |

## 未知 / 兜底错误 {#未知-兜底错误}

| 错误码 | 枚举名 | HTTP 状态码 | 说明 |
| ---: | --- | ---: | --- |
| 90001 | `UNKNOWN_ERROR` | 500 | 未知错误 |
| 90002 | `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |


## 使用约定

1. 后端抛出业务异常时，应优先使用 `BusinessError(detail, code=ErrorCode.XXX)`。

2. HTTP 状态码仅作为传输层语义，业务识别应以 `code` 字段为准。

3. 前端判断具体错误时，应使用 `ErrorCode.XXX`，避免对 `msg` 或 HTTP 状态码做字符串匹配。

4. 新增错误码需同步更新 `apps/frontend/src/shared/constants/errorCode.ts`。
