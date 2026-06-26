# Plan: 内容审核 Agent 监控页面

## Context

内容审核 Worker 每次运行都通过 `AgentMonitorSession(scenario="content_moderation")` 写入完整的 Agent 监控数据（运行记录 + 事件时间线），后端查询 API 已支持按 `scenario` 筛选。但管理后台目前只有「AI 对话监控」页面（固定 `scenario=ai_conversation`），管理员无法在 UI 中按审核场景查看 Agent 运行记录。

## Approach

复用现有 `AgentMonitorListComponents` 和 `AgentRunDetailModal` 组件，创建一个新页面 `AdminContentModerationMonitorPage`，除 `scenario` 固定为 `"content_moderation"` 及页面标题不同外，其余逻辑与 `AdminAIConversationMonitorPage` 完全相同。

## Files to modify

### 1. 新建：`pages/admin/AdminContentModerationMonitorPage.tsx`
- 从 `AdminAIConversationMonitorPage.tsx` 复制结构
- `scenario` 参数从 `"ai_conversation"` 改为 `"content_moderation"`
- 页面标题改为「内容审核监控」
- 副标题改为「查看每次自动审核的提示词、模型输出和审核判决流转。」

### 2. 修改：`App.tsx`
- 新增 import
- 新增 route `<Route path="/admin/agent-monitor/content-moderation" element={<AdminContentModerationMonitorPage />} />`

### 3. 修改：`pages/admin/AdminSideNav.tsx`
- 新增导航项 `{ to: "/admin/agent-monitor/content-moderation", icon: ShieldCheck, label: "内容审核监控" }`

## Verification
- TypeScript 类型检查 `npx tsc --noEmit`
- 前端构建 `npm run build`
- 前端测试 `npm test`（126 项全部通过）
