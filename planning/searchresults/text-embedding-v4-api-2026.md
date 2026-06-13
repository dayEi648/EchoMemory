# 阿里云 text-embedding-v4 API 调研（2026-06）

来源：阿里云官方文档与第三方接入示例（搜索日期 2026-06-13）。

## 关键结论

- 模型 ID：`text-embedding-v4`
- 服务入口：阿里云 DashScope（百炼）
- OpenAI 兼容端点：
  - 北京：`https://dashscope.aliyuncs.com/compatible-mode/v1`
  - 国际（新加坡）：`https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- API Key：DashScope API Key（通常配置为 `DASHSCOPE_API_KEY`）
- 默认维度：**1024**
- 可选维度：64 / 128 / 256 / 512 / 768 / 1024 / 1536 / 2048
  - 1536 与 2048 仅 `text-embedding-v4` 支持
  - 官方推荐通用场景使用 1024 维
- 单次请求最多支持 **25 条**输入
- 调用方式：OpenAI SDK 的 `client.embeddings.create(model="text-embedding-v4", input=[...], dimensions=1024)`

## 项目采用方式

- 后端通过 OpenAI SDK 访问 DashScope OpenAI 兼容接口，复用已引入的 `openai` 依赖。
- 默认配置：
  - 模型：`text-embedding-v4`
  - 维度：1024
  - base_url：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- API Key、base_url、模型、维度、批次大小均通过环境变量配置。
