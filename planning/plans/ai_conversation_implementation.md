# AI 对话流程实现方案

## 1. 需求回顾

- 基于 LangGraph 构建后端 AI 对话流程。
- 当前仅实现 AI 对话与对话记录存储机制，**不实现工具调用、RAG、长期记忆**等能力，但数据结构预留扩展空间。
- 使用 PostgreSQL 存储对话元数据；消息通过 LangGraph Checkpointer 持久化到 PostgreSQL，支持回退与附加状态存储。
- 消息类型需覆盖 `system`、`human`、`ai`、`tool`。
- 使用 Redis 做短期缓存，提高读取性能。
- 所有提示词提取到独立文件，便于查看维护。

## 2. 现状与约束

- 后端已具备：FastAPI + SQLAlchemy 2.0（asyncpg）+ PostgreSQL + Redis + `DeepSeekClient`（`core/llm.py`）。
- 已安装 `langgraph==1.2.4`、`langchain==1.3.4`、`langchain-core==1.4.2`。
- **未安装** `langgraph-checkpoint-postgres`，因此当前没有 `AsyncPostgresSaver`；需要新增依赖以使用 Postgres Checkpointer。
- 项目采用 `uv.lock` + `pyproject.toml` 管理依赖，开发环境使用国内镜像。
- 已有私信会话表 `conversations` / `direct_messages`，AI 对话使用全新独立模型，避免混淆。
- 测试使用 `echomemory_test` 数据库 + `FakeRedis`。

## 3. 技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| LangGraph Checkpointer | `AsyncPostgresSaver`（`langgraph-checkpoint-postgres`） | 官方实现，自动管理 `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` 表，支持时间旅行与状态回退。 |
| 异步 DB 驱动 | asyncpg（业务）+ psycopg v3（checkpointer） | 业务库继续使用 asyncpg；checkpointer 独立连接池使用 psycopg v3，两者互不干扰。 |
| LLM 调用 | 直接复用 `DeepSeekClient` | 在 LangGraph 节点内调用 `core/llm.py` 的客户端，避免再封装 LangChain ChatModel。 |
| 消息格式 | `langchain_core.messages.*` | 与 LangGraph 原生状态兼容，天然支持 `SystemMessage`、`HumanMessage`、`AIMessage`、`ToolMessage`。 |
| 缓存 | Redis | 缓存会话列表与单会话消息列表，写入时失效。 |
| 提示词 | Markdown 文件 | 存放于 `src/echomemory_backend/ai/prompts/`。 |

## 4. 数据模型

### 4.1 `ai_conversations`（业务表）

存储对话元数据，真正的消息内容由 LangGraph Checkpointer 保存。

```text
id              BigInteger PK
user_id         BigInteger FK -> users.id (CASCADE)
title           String(200)
model           String(50)      # 当前会话使用的模型，如 deepseek-v4-flash
status          SmallInteger    # 0=ACTIVE, 1=ARCHIVED, 2=DELETED
thread_id       String(64)      # LangGraph thread_id，默认等于 id 的字符串
updated_at      DateTime(timezone=True)
created_at      DateTime(timezone=True)
```

索引：`(user_id, status, updated_at)` 用于列表查询。

### 4.2 Checkpointer 表

由 `AsyncPostgresSaver.setup()` 自动创建：

- `checkpoints`
- `checkpoint_blobs`
- `checkpoint_writes`

这些表由 LangGraph 内部维护，业务代码不直接读写。

## 5. LangGraph 状态与流程

### 5.1 状态定义

```python
class AIConversationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    metadata: dict  # 预留，用于后续工具结果、用户画像等
```

### 5.2 流程

```
[入口] -> chatbot_node -> [END]
```

- `chatbot_node`：
  1. 从 `state["messages"]` 过滤出可发送给 LLM 的消息（`SystemMessage`、`HumanMessage`、`AIMessage`；`ToolMessage` 暂不透传）。
  2. 转换为 `core.llm.ChatMessage`。
  3. 调用 `DeepSeekClient.chat()`。
  4. 将返回的 `AIMessage`（含 `reasoning_content` 附加字段）追加到状态。

### 5.3 Checkpointer 集成

- 每个会话的 `thread_id` 固定为 `str(conversation.id)`。
- 调用 `graph.ainvoke(..., config={"configurable": {"thread_id": thread_id}})` 时自动写 checkpoint。
- 读取历史时通过 `graph.aget_state(config)` 获取完整状态。

## 6. Redis 缓存策略

键前缀与 TTL：

| 键 | 内容 | TTL |
|--|--|--|
| `ai:conv:list:{user_id}` | 用户会话列表 JSON | 5 min |
| `ai:conv:msgs:{conversation_id}` | 会话消息列表 JSON | 5 min |

写入/删除会话、发送消息时，同步删除对应缓存键。

## 7. 目录与文件规划

```
apps/backend/src/echomemory_backend/
├── ai/
│   ├── __init__.py
│   ├── checkpointer.py        # AsyncPostgresSaver 生命周期
│   ├── graph.py               # StateGraph 定义与节点
│   ├── prompts/
│   │   └── system.md          # 系统提示词
│   └── prompts.py             # 提示词加载器
├── api/v1/endpoints/
│   └── ai_conversation.py     # 路由
├── core/
│   ├── ai_cache.py            # Redis 缓存封装
│   └── config.py              # 新增 AI 相关配置
├── models/
│   └── ai_conversation.py     # AIConversation ORM
├── schemas/
│   └── ai_conversation.py     # Pydantic Schema
└── services/
    └── ai_conversation_service.py
```

## 8. API 设计

前缀：`/api/v1/ai/conversations`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 分页列出当前用户会话 |
| POST | `/` | 创建新会话，可附带首条消息 |
| GET | `/{id}/messages` | 获取会话消息列表 |
| POST | `/{id}/messages` | 发送消息并获取 AI 回复 |
| DELETE | `/{id}` | 软删除会话 |

## 9. 依赖变更

- `pyproject.toml` 新增：`"langgraph-checkpoint-postgres"`
- 运行 `uv add langgraph-checkpoint-postgres` 同步 `uv.lock`。

## 10. 测试策略

- 新增 `tests/test_ai_conversation.py`。
- 使用 `MemorySaver` 替代 `AsyncPostgresSaver`（通过 monkeypatch）。
- Mock `DeepSeekClient.chat` 返回固定响应。
- 覆盖：创建会话、发送消息、消息列表、缓存失效、checkpoint 回读。

## 11. 待确认决策

1. 是否接受新增 `langgraph-checkpoint-postgres` 依赖？（推荐：接受，否则需自研 checkpoint 表，成本高）
2. 会话标题生成策略：首条消息截断 50 字符作为标题，还是调用 LLM 生成？（推荐：首条消息截断，简单且可后续替换）
3. 默认使用 `deepseek-v4-flash` 还是 `deepseek-v4-pro`？（推荐：默认 flash，可在创建会话时指定）
4. 当前是否实现流式响应？（推荐：本期仅实现非流式，接口结构预留流式扩展）
