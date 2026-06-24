# DeepSeek 模型配置核验（2026-06-20）

## 核验目的

确认用户画像服务中使用的 `deepseek-v4-flash` 模型 ID 及 thinking 参数在当前
DeepSeek 官方 API 中仍受支持。

## 官方资料

- Models & Pricing: https://api-docs.deepseek.com/quick_start/pricing
- List Models API: https://api-docs.deepseek.com/api/list-models
- Create Chat Completion: https://api-docs.deepseek.com/api/create-chat-completion

## 结论

- 官方定价页当前列出 `deepseek-v4-flash`，并说明旧别名
  `deepseek-chat` / `deepseek-reasoner` 将于 2026-07-24 15:59 UTC
  弃用。
- Chat Completion 文档支持通过 `thinking.type` 使用
  `enabled` / `disabled` 控制思考模式。
- 当前仓库配置的 `deepseek-v4-flash` 与 `thinking.type=disabled`
  组合符合官方接口。
- 本地开发配置已通过一次真实 API 冒烟调用：判断请求返回布尔结果，画像生成请求
  返回非空文本。
