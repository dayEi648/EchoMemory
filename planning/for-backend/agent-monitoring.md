# Agent 监控接入指南

## 核心结构

- `agent_runs`：一次 Graph、Chain 或独立 Agent 工作流运行。
- `agent_events`：运行内按 `sequence` 排序的事件。
- `scenario`：稳定的业务场景标识，例如 `ai_conversation`。
- `workflow_type` / `workflow_name`：技术工作流类型和名称。

用户标识为运行时快照，不建立 `users` 外键。用户软删除或硬删除后，监控记录继续保留。

## 新场景接入

1. 为新场景确定稳定的 `scenario`，不要复用页面标题或临时类名。
2. 在工作流入口创建并 `start()` 一个 `AgentMonitorSession`。
3. 将 `AgentMonitorCallbackHandler` 放入 LangChain / LangGraph `callbacks`。
4. 使用 `bind_monitor()` 包裹实际执行过程，使节点和业务服务能读取当前监控上下文。
5. 在框架 callback 无法表达业务语义的位置调用 `record_event()`：
   - 提示词初始化和渲染；
   - 实际模型请求准备；
   - 消息投递；
   - checkpoint 摘要变化；
   - 长期记忆评估和更新；
   - 业务级确定性分支。
6. 成功调用 `complete()`；失败调用 `fail()` 后继续传播原业务异常。

## 事件命名

使用 `<领域>.<过去式或状态>`：

- `prompt.initialized`
- `prompt.rendered`
- `message.received`
- `llm.request.prepared`
- `llm.response.completed`
- `tool.started`
- `tool.completed`
- `memory.short_term.updated`
- `memory.long_term.updated`

不要把每个流式 token 单独写成事件。

## 故障策略

- 监控写入通过独立异步队列完成。
- 队列满、序列化异常、数据库异常和重试耗尽都不得阻断 Agent。
- writer 使用有限指数退避重试；最终失败写入系统错误日志。
- 应用关闭时先排空监控队列，再关闭数据库日志设施。

## 数据安全

- 序列化器递归脱敏 token、password、secret、authorization 等字段。
- 大文本和大集合会截断并保留原始长度标记。
- 列表 API 不返回完整输入输出；只有管理员详情接口返回。
- 新工具若包含额外凭证字段，字段名应使用 `*_token`、`*_secret`、`*_api_key` 等可识别命名。

## 场景专属表

默认不要为新场景复制运行表和事件表。

只有当某场景出现稳定、必须约束或高频索引的专属字段时，才增加以 `agent_runs.id` 为主键/外键的一对一扩展表。管理后台可为场景建立独立页面，但应复用通用查询 API 和时间线组件。

