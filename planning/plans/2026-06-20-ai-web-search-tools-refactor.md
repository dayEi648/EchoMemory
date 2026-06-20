# AI 联网搜索与工具基础设施修复计划

## 目标

把现有联网搜索从 IQS REST 直连改为 IQS Search MCP，并建立可验证的工具注册、
动态授权和并发控制基础设施，同时修复 DeepSeek/LangChain 工具调用协议问题。

## 架构决策

- 使用本地 `@tool search_web` 作为稳定接口，内部调用 IQS MCP
  `common_search`。
- 注册中心只维护不可变元数据、工具解析和单工具并发配额；不持有业务状态。
- chatbot 节点按当前 state 动态绑定工具；tool 节点使用同一上下文再次解析，
  拒绝未授权或未注册调用。
- `allow_parallel=False` 表示同一模型响应中的全部工具调用串行执行；
  `max_concurrency` 使用注册中心级异步信号量，在并发会话之间也生效。
- DeepSeek 消息模型保留 assistant tool calls；流式响应逐块转发内容与
  tool-call fragments，避免启用工具后失去流式输出。

## 任务

### 1. 工具注册中心契约

验收：

- 重复注册、元数据名称不一致、非法并发数会明确报错。
- tags 使用不可变集合。
- 可按上下文解析并验证单个工具。
- `max_concurrency` 在真实并发执行中生效。

验证：`pytest tests/test_tool_registry.py`

### 2. IQS MCP 搜索工具

验收：

- 使用 `MultiServerMCPClient`、HTTP transport、`X-API-Key`。
- 调用远程 `common_search`，本地 schema/description 来自 `@tool`。
- 空 query、超长 query、缺少 API key、MCP 连接失败有稳定结果。

验证：`pytest tests/test_web_search_tool.py`

### 3. 元数据感知工具执行节点

验收：

- 当前上下文不可用的工具不会执行。
- 串行标志和单工具并发上限真实生效。
- 工具异常不泄漏内部异常文本。

验证：新增工具节点单元测试。

### 4. DeepSeek 工具调用协议

验收：

- assistant tool calls 会序列化回模型请求。
- 流式 tool-call 参数片段能正确合并。
- 绑定工具后，普通文本回复仍保持 token/chunk 流式输出。

验证：扩展 `tests/test_deepseek_tool_calling.py`。

### 5. 回归检查

验收：

- AI 对话相关测试通过。
- 后端完整测试通过或明确记录与本次无关的失败。
- `planning/directory.md` 与实际新增基础设施一致。

## 风险与控制

- MCP 远程服务不可用于自动化测试：在 MCP 客户端边界使用 fake tool，不发外网。
- 全局并发信号量跨 event loop 可能出错：按运行中的 event loop 延迟创建。
- 工具历史截断可能产生孤立 ToolMessage：按完整 tool-call 交互边界截断。

## 两轮决策复核

### 第一轮

- REST 直连不满足 MCP 要求，必须替换。
- 仅绑定阶段过滤不是授权边界，执行阶段必须复核。
- 仅保存并发元数据没有行为价值，必须由测试证明生效。

### 第二轮（实施前）

- 不直接把远程 MCP tool 暴露给模型，保留本地 `search_web`，避免远程命名和
  schema 变化扩散到提示词、测试与历史消息。
- 当前只有一个工具，不引入通用插件发现、数据库配置或复杂依赖注入框架。
- 不在本任务加入搜索结果缓存、重试、监控系统或 query 扩展；这些都超出需求，
  可在后续基于元数据和 MCP interceptor 扩展。

