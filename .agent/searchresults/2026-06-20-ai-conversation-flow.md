# AI 基础对话流程官方资料核对（2026-06-20）

## 结论

- LangGraph checkpointer 用于保存线程级短期状态；初始化线程不应通过执行 chatbot 节点来制造 checkpoint。
- LangChain 的流式消息协议支持将模型推理与最终文本作为不同内容类型处理，前端适合用可折叠区域展示推理。
- DeepSeek V4 的 thinking mode 通过请求参数显式启用或禁用；推理内容由 `reasoning_content` 返回，最终回答由 `content` 返回，不需要让模型生成自定义 XML 标签。
- DeepSeek V4 thinking mode 不使用 `temperature`；启用 thinking 时应避免把该参数作为有效控制项。
- DeepSeek V4 Flash 与 Pro 均支持 Thinking / Non-Thinking 双模式。

## 官方来源

- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangChain Streaming: https://docs.langchain.com/oss/python/langchain/streaming
- LangChain Reasoning tokens: https://docs.langchain.com/oss/python/langchain/frontend/reasoning-tokens
- DeepSeek Thinking Mode: https://api-docs.deepseek.com/guides/thinking_mode
- DeepSeek Chat Completion API: https://api-docs.deepseek.com/api/create-chat-completion
- DeepSeek V4 Preview Release: https://api-docs.deepseek.com/news/news260424
