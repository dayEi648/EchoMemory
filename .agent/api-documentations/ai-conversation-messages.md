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

## 结构化附件

最终 `ai` 消息可包含 `attachments` 数组。附件来自 checkpoint 中对应工具消息的
artifact，因此重新打开历史会话时仍可恢复。

当前附件类型：

- `music_card`：音乐卡片，可进入详情或在对话页播放。
- `playlist_card`：歌单卡片，可进入歌单详情。
- `album_card`：专辑卡片，可进入专辑详情。
- `confirmation_card`：收藏/取消收藏二次确认卡片。

所有附件包含 `version: 1`。资源 ID 仅供客户端路由、播放和后续工具调用，不应由
AI 在自然语言回复中向用户展示。

## 流式附件

SSE 增加 `attachment` chunk：

```json
{
  "type": "attachment",
  "data": "",
  "model": "deepseek-v4-flash",
  "meta": {
    "attachment": {
      "version": 1,
      "type": "music_card",
      "items": []
    }
  }
}
```

客户端应立即渲染该附件；后续读取历史时，以消息 `attachments` 字段为准。

## 收藏二次确认

收藏或取消收藏分为两步：

1. AI 工具生成 `confirmation_card`，此时不修改业务数据。
2. 用户点击卡片确认按钮后，客户端在发送确认消息时通过请求体
   `confirmation_token` 字段提交卡片中的签名凭证。

普通文字消息不携带 `confirmation_token`，不能触发写操作。凭证绑定当前用户、
资源与动作，短时有效且只能成功使用一次。
