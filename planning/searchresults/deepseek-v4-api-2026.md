# DeepSeek V4 API 调研（2026-06）

来源：官方发布与第三方评测汇总（搜索日期 2026-06-13）。

## 关键结论

- DeepSeek 于 2026-04-24 发布 V4 系列模型，提供两个官方 API model ID：
  - `deepseek-v4-pro`：旗舰推理 / Agent 模型，1.6T 总参 / 49B 激活。
  - `deepseek-v4-flash`：快速经济模型，284B 总参 / 13B 激活。
- API 端点保持 OpenAI 兼容，base URL 为 `https://api.deepseek.com`。
- 两种模型均支持 1M 上下文，支持 Thinking / Non-Thinking 模式。
- 启用思考模式：请求中设置 `reasoning_effort="high"` 与 `extra_body={"thinking": {"type": "enabled"}}`。
- 思考内容通过响应 `message.reasoning_content` 字段返回，与最终 `content` 并列。
- 旧 ID `deepseek-chat`、`deepseek-reasoner` 将于 2026-07-24 弃用。

## 项目采用方式

- 后端使用 OpenAI Python SDK 访问 DeepSeek。
- 默认模型配置：
  - 思考模型：`deepseek-v4-pro`
  - 快速模型：`deepseek-v4-flash`
- API key、base_url、model ID 均通过环境变量配置，默认 base_url 使用官方节点。
