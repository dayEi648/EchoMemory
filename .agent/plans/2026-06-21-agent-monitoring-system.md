# Agent 监控体系实施计划

> 状态：已实施（2026-06-21）

## 1. 目标

为 echomemory 建立自有 Agent 监控体系，覆盖当前 AI 对话 Graph，并能低成本扩展到后续 Graph / Chain 场景。

监控必须记录：

- 一次 Agent 运行从开始到结束的状态、耗时和错误；
- 运行输入与最终输出；
- Graph / Chain / 节点的父子执行关系；
- 实际发送给模型的消息、系统提示词、动态工具定义和提示词变化；
- 消息流转与关键 state 更新；
- 工具请求、参数、结果、错误和耗时；
- 短期记忆 checkpoint 相关变化；
- 长期记忆判断、更新前后内容和结果；
- 模型、token usage、配置及其它调试所需元数据。

## 2. 已确认现状

### 项目定位与形态

- Windows 桌面端为主，Tauri 2 + React 19 前端，FastAPI + PostgreSQL 后端。
- AI 基础设施已分为可复用的 `ai/tools` 和 `ai/graphs`。
- 当前只有 `conversation` Graph；工具注册中心已支持权限、标签、并发与只读约束。
- 管理后台已有系统日志页面、管理员鉴权、分页列表与详情弹窗模式。

### 当前 AI 对话链路

1. API 创建或读取 `AIConversation` 元数据。
2. `build_graph()` 按会话模型构建 Graph。
3. 系统提示词写入 LangGraph checkpoint。
4. 用户消息进入 `chatbot`。
5. `chatbot` 动态解析工具、过滤上下文并流式调用 DeepSeek。
6. 如模型产生工具调用，进入 `tools`，之后回到 `chatbot`。
7. Graph 状态由 Postgres checkpointer 保存。
8. 每累计 4 条用户消息，`user_profile_service` 判断并可能更新长期画像。

### 现有可观测性缺口

- `system_logs` 只记录 WARNING 以上系统错误，不是 Agent 运行轨迹。
- checkpoint 保存最终状态，但不提供适合管理后台查询的运行时间线。
- 当前 SSE 只消费 `messages`，没有节点、状态、工具和记忆的统一记录。
- 模型客户端已有 usage，但 `DeepSeekChatModel` 没有把 usage 完整投影到统一监控数据。
- 标题生成和用户画像模型调用不属于主 Graph 节点，必须显式纳入监控。

## 3. 核心设计决策

### 3.1 不按场景复制核心表

采用两张通用核心表：

#### `agent_runs`

表示一次顶层或嵌套 Agent / Graph / Chain 运行。

核心字段：

- `id`
- `trace_id`
- `parent_run_id`
- `scenario`
- `workflow_type`
- `workflow_name`
- `workflow_version`
- `user_id`
- `subject_type` / `subject_id`
- `thread_id`
- `status`
- `model`
- `input`
- `output`
- `error`
- `metadata`
- `started_at` / `ended_at` / `duration_ms`
- 聚合 token 与事件数量

#### `agent_events`

表示运行中的有序事件。

核心字段：

- `id`
- `run_id`
- `sequence`
- `event_type`
- `component_type`
- `component_name`
- `status`
- `payload`
- `error`
- `started_at` / `ended_at` / `duration_ms`

`payload` 使用 JSONB 保存不同事件的结构化详情；稳定且常用的筛选字段保留为普通列。

### 3.2 场景隔离方式

- `scenario="ai_conversation"`：当前 AI 对话。
- 后续可新增 `agent_review`、`comment_agent` 等稳定场景标识。
- 管理后台每个场景使用独立路由和页面标题，但复用通用监控 API 与 UI 组件。
- 未来只有在场景专属字段需要高频查询、约束或关联时，才增加一对一扩展表。

### 3.3 采集层分工

#### 通用自动采集

通过通用监控上下文和 LangChain callback 采集：

- Graph / Chain / node 开始、结束、错误；
- LLM 开始、结束、错误；
- tool 开始、结束、错误；
- 父子运行关系、tags、metadata。

#### 显式业务采集

在无法由框架准确表达语义的位置记录：

- 系统提示词初始化；
- 模型调用前过滤后的真实消息列表；
- 动态工具列表和工具 schema；
- 确认凭证驱动的确定性工具调用；
- 用户可见消息与内部消息的投影变化；
- checkpoint 前后消息数量和状态摘要；
- 用户画像评估、跳过、更新前后值；
- 标题生成子流程。

### 3.4 采集粒度

- 不把每个 token 单独写入数据库，避免巨量写放大。
- 记录完整模型输入、聚合后的 reasoning / content / tool calls、usage 与耗时。
- 消息级、节点级、工具级和记忆级事件独立记录。
- 对大字段设置可配置长度上限，并在截断时写入 `is_truncated` 与原始长度。

### 3.5 API 契约

- `GET /api/v1/admin/agent-monitor/scenarios`
- `GET /api/v1/admin/agent-monitor/runs`
  - 场景、用户、状态、模型、时间范围、关键词、游标分页
- `GET /api/v1/admin/agent-monitor/runs/{run_id}`
  - 运行摘要
- `GET /api/v1/admin/agent-monitor/runs/{run_id}/events`
  - 按 sequence 返回时间线

列表默认不返回完整提示词与输入输出；详情接口才返回大字段。

### 3.6 前端形态

当前阶段新增独立“AI 对话监控”页面：

- 路由：`/admin/agent-monitor/ai-conversation`
- 顶部筛选：时间、用户、状态、模型、关键词；
- 列表：开始时间、用户、会话、模型、状态、耗时、token、工具次数；
- 详情：运行摘要 + 可折叠时间线；
- 事件按消息、提示词、模型、工具、记忆、错误使用明确图标和状态标签；
- JSON / 文本使用可复制、可折叠、可滚动的详情块。

后续新增场景时，新页面仅固定 `scenario` 并调整展示列，不复制底层数据访问逻辑。

## 4. 实施任务

### Task 1：定义监控契约与纯逻辑测试

验收标准：

- 事件类型、状态、场景和序列化结构有稳定类型定义。
- 敏感字段处理、长度截断、消息序列化先有失败测试。
- 不依赖 LangGraph 内部私有 API。

验证：

- 运行新增监控单元测试，确认 RED 后再实现至 GREEN。

### Task 2：建立数据库模型与迁移

验收标准：

- `agent_runs`、`agent_events` 具有约束、外键和匹配查询模式的复合索引。
- `scenario + started_at + id`、`user_id + started_at + id` 可高效分页。
- 迁移 upgrade / downgrade 可执行。

验证：

- ORM 建表测试；
- Alembic upgrade 测试；
- PostgreSQL 约束与级联行为测试。

### Task 3：实现通用采集器

验收标准：

- 支持 run start/end/fail 和有序事件追加。
- 支持父子 run、ContextVar 传播、批量写入和异常隔离。
- 同一运行并发工具事件不会产生重复 sequence。

验证：

- 并发顺序、嵌套运行、异常和截断测试。

### Task 4：接入 LangChain / LangGraph 生命周期

验收标准：

- Graph、node、LLM、tool 的开始/结束/错误可自动记录。
- 框架回调与现有 SSE 可并存。
- 实际模型输入、工具定义、输出和 usage 可被采集。

验证：

- 使用 MemorySaver 和 FakeDeepSeek 的集成测试；
- 非流式与流式路径均覆盖。

### Task 5：接入 AI 对话业务事件

验收标准：

- 创建会话、发送消息、确认工具调用均产生顶层运行。
- 系统提示词、消息流转和 checkpoint 摘要被记录。
- 标题生成、画像评估与画像更新作为子流程或事件被记录。
- 现有 AI 对话响应协议不变。

验证：

- 扩展 `test_ai_conversation.py`、`test_tool_node.py`、`test_user_profile.py`。

### Checkpoint A

- 后端相关测试全部通过。
- 监控关闭或写入失败时的行为符合用户确认策略。
- 现有 AI 对话回归测试通过。

### Task 6：实现管理员查询 API

验收标准：

- 仅管理员可访问。
- 列表支持场景、用户、状态、模型、时间和关键词筛选。
- 列表采用稳定游标分页；详情事件按 sequence 排序。
- 返回结构不泄露数据库或框架内部对象。

验证：

- 权限、筛选、分页、详情和不存在资源测试。

### Task 7：实现 AI 对话监控管理页面

验收标准：

- 管理后台导航出现“AI 对话监控”。
- 页面可筛选不同时间和用户的运行。
- 详情时间线清晰展示提示词、消息、模型、工具、记忆与错误事件。
- 有加载、空、错误状态，并支持键盘访问。

验证：

- API client 与组件测试；
- TypeScript、ESLint、Vite build；
- 浏览器检查桌面与窄屏布局、控制台和网络请求。

### Task 8：文档与最终复核

验收标准：

- 更新目录文档、后端参考文档和 API 文档。
- 记录如何为新 Graph / Chain 注册场景和埋点。
- 完成第二轮反向代码审查，修复有效问题。

验证：

- 后端完整测试；
- 前端完整测试、lint、build；
- Alembic head 校验；
- `git diff --check`。

## 5. 风险与控制

| 风险 | 影响 | 控制 |
|---|---|---|
| 完整提示词和消息包含隐私或凭证 | 高 | 敏感键递归脱敏、字段长度上限、仅管理员详情可见、明确保留策略 |
| 每 token 入库造成写放大 | 高 | 聚合模型输出，不持久化 token 级事件 |
| 监控写入拖慢 SSE | 高 | 独立会话、批量事件、短事务，主流程与监控事务解耦 |
| 监控失败掩盖主业务错误 | 中 | 独立错误日志和明确失败策略 |
| JSONB 无边界增长 | 中 | 结构约束、截断标记、后续按真实数据量决定归档/分区 |
| 依赖 LangGraph 私有事件格式 | 高 | 公共 callback 接口 + 显式业务事件，不解析私有 checkpoint 表 |
| 不同场景复制表和页面逻辑 | 中 | 通用核心表、通用 API、场景配置化 UI |

## 6. 第一轮方案反向检查

### 被否决的方案

1. **每个 Agent 场景单独建运行表和事件表**
   - 会复制索引、API、迁移和 UI 逻辑；
   - 跨场景统计困难；
   - 新场景接入成本高。

2. **直接把 LangGraph checkpoint 当监控数据源**
   - checkpoint 是状态恢复设施，不是运行审计；
   - 无稳定的节点耗时、错误、工具和提示词变化查询模型；
   - 会耦合 LangGraph 内部存储格式。

3. **把每个流式 token 作为事件写数据库**
   - 数据量和事务开销不成比例；
   - 管理后台调试价值有限。

4. **只依赖 LangChain callback**
   - 无法准确表达用户画像更新、标题生成和 prompt 过滤后的业务语义；
   - 必须与显式业务事件组合。

### 用户确认结果（2026-06-21）

1. 用户被软删除或硬删除后，监控记录完整保留，不匿名化、不级联删除。
2. 监控写入失败时 Agent 主流程继续执行；监控使用异步重试，最终失败写入系统错误日志。
3. 不进行外部模型交叉复核，按单模型反向检查结果实施。

## 7. 实施验证结果

- Alembic 已升级至 `6f4c2a8d1b90 (head)`。
- 后端完整测试：660 项通过。
- 最终监控相关回归：68 项通过。
- 前端完整测试：124 项通过。
- 最终管理后台相关测试：17 项通过。
- 前端 TypeScript、ESLint 和生产构建通过。
- 真实运行中的登录、列表、详情和事件 API 均返回成功信封。
- 国内 npm 镜像不实现 audit API，因此 `npm audit` 无法完成；未切换到境外 registry。
- 应用内浏览器连接因运行环境缺少沙箱元数据而失败，未擅自切换到独立 Playwright；真实浏览器视觉检查未完成。
