# Agent 监控体系官方资料核对（2026-06-21）

## 核对范围

- 当前仓库实际安装版本：
  - `langgraph==1.2.4`
  - `langchain==1.3.4`
  - `langchain-core==1.4.2`
  - `sqlalchemy==2.0.50`
- 目标：在不使用 LangSmith 等第三方监控平台的前提下，自建可扩展的 Agent / Graph / Chain 运行记录体系。

## 官方能力结论

### LangGraph 运行事件

LangGraph 的 `stream` / `astream` 支持多种运行投影，包括：

- `messages`：模型消息与 token 流；
- `updates`：每一步状态更新；
- `values`：完整状态值；
- `checkpoints`：checkpoint 事件；
- `tasks`：任务开始与结束；
- `debug`：调试级运行信息；
- `custom`：业务自定义事件。

当前项目的 AI 对话流只消费 `messages`，适合用户侧 SSE，但不足以单独构成完整审计。监控层需要使用独立回调与显式业务事件，不能把管理后台监控耦合到用户 SSE 协议。

### LangChain 回调

当前安装的 `BaseCallbackHandler` 暴露 chain、LLM、tool 等生命周期回调，并提供：

- `run_id`
- `parent_run_id`
- `tags`
- `metadata`
- 输入、输出与错误

这些字段可作为通用运行树和父子 span 的基础。但回调只能看到框架传递的对象；项目中模型调用前的消息过滤、工具动态绑定、用户画像更新等业务语义仍需显式埋点。

### LangGraph 记忆

官方区分：

- 短期记忆：线程级 state / checkpoint；
- 长期记忆：跨线程、面向用户或应用的持久状态。

当前项目与此一致：

- 短期记忆位于 LangGraph Postgres checkpointer；
- 长期记忆位于 `user_profiles`，由 `user_profile_service` 维护。

监控表不应替代任一记忆存储；它只记录运行事实、状态变化摘要和必要快照。

### PostgreSQL 事件表设计

PostgreSQL 官方与项目数据库规范支持：

- 时间字段使用 `timestamptz`；
- 外键列必须显式建立索引；
- 常用筛选采用“等值列在前、时间范围列在后”的复合索引；
- 不稳定、异构的事件详情使用 `jsonb`；
- 只有当事件表达到非常大规模并有明确保留/清理需求时才按时间分区，当前阶段不提前分区；
- 深分页应优先使用 `(created_at, id)` 游标分页。

## 对本项目的架构推论

1. 使用一组通用核心表，而不是每个 Agent 场景复制一套表：
   - 运行表：每次 Graph / Chain 调用一条；
   - 事件表：节点、模型、消息、工具、记忆、提示词、错误等按时间线记录。
2. 通过 `scenario` 区分 AI 对话、审核 Agent、评论 Agent 等场景。
3. 管理后台可以为每个场景建立独立页面，但复用同一查询 API、列表组件和详情时间线组件。
4. 只有未来某个场景出现稳定且必须独立索引的专属字段时，才增加场景扩展表；不复制核心运行/事件表。
5. 用户侧 SSE 仍只负责用户可见消息；监控采集不得改变现有流协议。

## 官方来源

- LangGraph Streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- LangGraph Memory: https://docs.langchain.com/oss/python/langgraph/add-memory
- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- LangChain Streaming: https://docs.langchain.com/oss/python/langchain/streaming
- LangChain Tools: https://docs.langchain.com/oss/python/langchain/tools
- PostgreSQL JSON Types / Indexing: https://www.postgresql.org/docs/current/datatype-json.html
- PostgreSQL Multicolumn Indexes: https://www.postgresql.org/docs/current/indexes-multicolumn.html
- PostgreSQL Table Partitioning: https://www.postgresql.org/docs/current/ddl-partitioning.html
- PostgreSQL Partial Indexes: https://www.postgresql.org/docs/current/indexes-partial.html

