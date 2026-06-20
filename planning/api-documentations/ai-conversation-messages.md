# AI 会话消息历史 API

## 获取会话消息

`GET /api/v1/ai/conversations/{conversation_id}/messages`

### 消息可见性

- 普通用户（USER）与 VIP：服务端固定只返回 `human` 和最终自然语言
  `ai` 消息。客户端传入内部消息类型不会扩大权限。
- 管理员（ADMIN）与超级管理员（SUPER_ADMIN）：
  - 未提供筛选参数时，同样只返回 `human` 和最终 `ai` 消息。
  - 显式提供 `message_types` 时，可筛选查看完整 checkpoint 消息。

### 查询参数

`message_types` 是可重复参数，允许值：

- `system`
- `human`
- `ai`
- `tool`

示例：

```text
GET /api/v1/ai/conversations/123/messages
  ?message_types=system
  &message_types=human
  &message_types=ai
  &message_types=tool
```

管理员筛选 `ai` 时会包含发起工具调用的中间 AI 消息，其 `tool_calls`
字段保存调用信息。`tool` 消息包含 `tool_call_id` 与工具 `name`。

### 安全边界

筛选权限由后端根据当前登录用户角色计算。前端是否展示筛选控件不作为权限判断。
LangGraph checkpoint 中始终保留完整消息序列，API 只生成不同的读取投影。

