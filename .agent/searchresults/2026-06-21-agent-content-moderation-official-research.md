# Agent 内容审核机制官方资料核验

核验日期：2026-06-21

## 结论

1. 审核结果应使用受约束的结构化数据，并在应用边界通过 Pydantic 再次校验，不能直接信任模型自然语言输出。
2. 审核流程属于固定步骤工作流，不需要让模型自主选择工具；LangGraph 官方将固定代码路径定义为 workflow，适合拆分为加载内容、模型评分、结果校验、业务落库等节点。
3. LangGraph checkpointer 可提供图执行状态持久化，但“内容创建后可靠入队”仍需要与业务事务一致的任务记录。当前项目最小且可靠的方案是 PostgreSQL 持久化审核任务表。
4. PostgreSQL 官方明确说明 `SKIP LOCKED` 适用于多个消费者访问队列式表时避免锁竞争；SQLAlchemy 2.x 可通过 `with_for_update(skip_locked=True)` 生成对应语句。

## 对本项目的建议

- 创建内容和创建审核任务必须在同一个数据库事务中提交，避免“内容已发表但任务丢失”。
- Worker 从任务表批量领取待处理任务，使用行锁与 `SKIP LOCKED` 支持多进程/多实例并发。
- 任务需要明确状态、尝试次数、下次重试时间、锁定时间、错误摘要和关联的 Agent run id。
- 模型输出只作为候选审核结果；分值范围、档位映射和最终业务动作由确定性代码执行。
- Agent 监控复用现有 `agent_runs` / `agent_events`，新增稳定场景标识，例如 `content_moderation`。

## 官方资料

- LangChain Structured Output:
  https://docs.langchain.com/oss/python/langchain/structured-output
- LangGraph Workflows and Agents:
  https://docs.langchain.com/oss/python/langgraph/workflows-agents
- LangGraph Persistence:
  https://docs.langchain.com/oss/python/langgraph/persistence
- PostgreSQL SELECT / SKIP LOCKED:
  https://www.postgresql.org/docs/current/sql-select.html
- SQLAlchemy 2.x SELECT / with_for_update:
  https://docs.sqlalchemy.org/en/latest/core/selectable.html
