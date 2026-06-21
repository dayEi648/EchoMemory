# Agent 监控管理 API

所有接口要求管理员或超级管理员权限。

## 列出场景

`GET /api/v1/admin/agent-monitor/scenarios`

返回已有场景、运行总数和最近运行时间。

## 查询运行

`GET /api/v1/admin/agent-monitor/runs`

查询参数：

- `scenario`
- `user_id`
- `status`: `RUNNING | SUCCEEDED | FAILED | CANCELLED`
- `model`
- `start_time`
- `end_time`
- `q`
- `cursor`
- `limit`: 1–100

结果按 `started_at DESC, id DESC` 排序，使用不透明游标分页：

```json
{
  "items": [],
  "total": 0,
  "next_cursor": null
}
```

## 获取运行详情

`GET /api/v1/admin/agent-monitor/runs/{run_id}`

在列表字段基础上返回：

- `input`
- `output`
- `error`
- `metadata`

## 获取事件时间线

`GET /api/v1/admin/agent-monitor/runs/{run_id}/events`

按 `sequence` 升序返回提示词、消息、模型、工具、记忆和错误事件。

