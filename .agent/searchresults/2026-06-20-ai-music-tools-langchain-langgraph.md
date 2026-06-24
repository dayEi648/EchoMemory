# AI 音乐 Tools 官方资料核对（2026-06-20）

## 结论

- LangChain `@tool` 默认使用函数 docstring 作为工具描述，并依据类型注解生成模型可见的输入 schema。
- 当前官方推荐使用 `ToolRuntime` 向工具注入会话 state、不可变 context、stream writer、tool call ID 等运行时信息；这些参数不会暴露给模型。
- 工具查询结果可返回结构化对象供模型继续分析；需要更新图状态时可返回 `Command`。
- 工具执行期间可以通过 stream writer 发送自定义结构化事件；调用图时可同时启用 `messages` 与 `custom` 流模式。
- LangGraph checkpoint 保存线程级状态。若推送卡片需要在历史会话中恢复，不能只依赖瞬时 custom 事件，还需要把可回放数据保存在 checkpoint 可读取的消息或状态中。
- LangGraph 官方建议分别测试图节点、部分图和完整图；本任务应覆盖工具单元测试、ToolNode/流协议集成测试和前端卡片交互测试。

## 对本项目的影响

- `user_id`、会话状态和 tool call ID 不应作为模型参数；应由运行时注入。
- 查询工具返回给模型的数据应精简，只保留用于判断、消歧和后续操作的字段。
- 推送工具需要同时满足：
  1. 实时通过 SSE custom 事件发送给前端；
  2. 在 checkpoint 中保留可回放表示；
  3. 不把前端展示字段全部污染模型上下文。
- 当前自定义 ToolNode 直接调用 `BaseTool.ainvoke`，尚未实现官方 ToolNode 的运行时参数注入，需要在开发中补齐或复用官方 ToolNode 能力。

## 官方来源

- LangChain Tools: https://docs.langchain.com/oss/python/langchain/tools
- LangChain Runtime: https://docs.langchain.com/oss/python/langchain/runtime
- LangChain Streaming: https://docs.langchain.com/oss/python/langchain/streaming
- LangGraph Streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- LangGraph Persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph Testing: https://docs.langchain.com/oss/python/langgraph/test
