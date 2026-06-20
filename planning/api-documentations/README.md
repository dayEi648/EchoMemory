# API 文档目录

本目录存放 echomemory 项目的 API 相关文档。

## 文件说明

| 文件 | 说明 |
| --- | --- |
| `error-codes.md` | 统一错误码与 HTTP 状态码规范。由后端脚本自动生成。 |
| `ai-conversation-messages.md` | AI 会话消息历史的角色权限与类型筛选契约。 |

## 错误码文档生成

```bash
cd apps/backend
python scripts/generate_error_code_doc.py
```

运行后会根据 `src/echomemory_backend/core/exceptions/codes.py` 中的 `ErrorCode` 枚举，
重新生成 `planning/api-documentations/error-codes.md`。

## 维护约定

1. 新增错误码时，先修改后端 `core/exceptions/codes.py`。
2. 同步修改前端 `apps/frontend/src/shared/constants/errorCode.ts`，保持数值一致。
3. 运行生成脚本更新本文档。
4. 后端抛出异常时使用 `BusinessError(detail, code=ErrorCode.XXX)`。
5. 前端判断错误时使用 `ErrorCode.XXX`，避免字符串匹配或魔法数字。
