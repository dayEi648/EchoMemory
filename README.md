# echomemory（回声记忆）

> 围绕 AI Agent 的本地桌面音乐客户端 + 云端 API 音乐平台。

echomemory 是一个以 Windows 桌面端为主要构建方向的智能音乐平台。它将传统音乐播放、社交与推荐能力，与基于大模型的 AI 助手、RAG 知识库、内容审核和 Agent 可观测性整合在同一套 monorepo 中，试图探索"Agent 原生音乐应用"的工程形态。

本仓库为**开发环境配置**，不是生产环境配置。请勿将本地 `.env`、密钥、数据库密码或 OSS/LLM API Key 提交到仓库。

---

## 目录

- [项目简介](#项目简介)
- [已实现的能力](#已实现的能力)
- [关键实现](#关键实现)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [开发指南](#开发指南)
- [测试](#测试)
- [故障排查](#故障排查)
- [相关文档](#相关文档)
- [如何贡献](#如何贡献)

---

## 项目简介

echomemory 由两部分核心组成：

- **后端（`apps/backend`）**：基于 FastAPI 的异步 API 服务，覆盖用户、音乐、专辑、歌单、评论、私信、通知、播放历史、推荐、管理后台、AI 对话、内容审核、RAG 与 Agent 监控等业务。
- **前端（`apps/frontend`）**：基于 Tauri 2 + React 19 + TypeScript + Vite 的桌面客户端，开发态由 Vite 提供页面服务，最终打包为 Windows 桌面应用。

项目采用 monorepo 组织，基础设施（PostgreSQL、Redis、Nginx）通过 `infra/` 下的 Docker Compose 与配置文件统一提供。

---

## 已实现的能力

### 音乐与内容

- 音乐、专辑、歌单、收藏、播放历史的基础 CRUD 与搜索
- "我喜欢的音乐"系统歌单与普通歌单的分离设计
- 评论、说说、私信、通知、关注等社交能力
- 每日推荐、私人雷达、热度排序等推荐入口
- 管理后台：用户管理、内容审核、音乐知识库、Agent 监控

### AI 与 Agent

- 基于 LangGraph 的 AI 对话工作流，支持工具调用循环与多轮状态持久化
- 可扩展工具注册表，已接入音乐检索、收藏变更、联网搜索、RAG 检索等工具
- 基于 RAG 的音乐知识库，支持文档解析、向量嵌入与语义检索
- 异步内容审核 Worker，对评论、说说等 UGC 进行自动审核
- Agent 监控基础设施：记录 Graph/Chain 运行、事件、LLM 用量，且不阻断主流程

---

## 关键实现

以下是项目里几处真正需要工程取舍、且对行为有决定性影响的实现细节。

### 1. AI 对话的状态投影与二次确认安全边界

对话历史从 LangGraph checkpoint 读取后，并不是直接返回给前端，而是经过 `_project_messages_for_view` 做视图投影：

- `ToolMessage` 对前端保持隐藏，但允许公开的 `artifact`（音乐卡片、歌单卡片、确认卡片）会被绑定到紧随其后的最终 AI 消息，从而支持历史会话恢复时正常展示卡片；
- 中间 AI 的工具调用消息可选择性过滤，避免用户看到 raw tool_calls；
- 早期误写入的孤立 AI 消息会被 `_remove_orphan_assistant_messages` 清理。

当 AI 要执行收藏/取消收藏等写操作时，不会直接调用写工具，而是先返回 `confirmation_card`。用户点击确认后，前端把 JWT 签名凭证注入运行时，`confirmation` 节点再把它转换为确定性的 `confirm_collection_change` 工具调用。该凭证：

- 使用 `SECRET_KEY` 签名，绑定用户、资源类型、资源 ID 与动作；
- 5 分钟过期；
- 通过 Redis `SET NX` 做原子占用，防止重放或并发执行。

相关代码：`apps/backend/src/echomemory_backend/services/ai_conversation_service.py`、`apps/backend/src/echomemory_backend/ai/tools/music_catalog.py`、`apps/backend/src/echomemory_backend/ai/tools/confirmation.py`、`apps/backend/src/echomemory_backend/ai/graphs/conversation/builder.py`

### 2. Agent 监控的旁路可观测性设计

监控不是简单打日志，而是一套不阻断主流程的可观测性设施：

- 使用 `ContextVar` 在当前异步执行链中绑定 `AgentMonitorSession`，业务代码通过 `get_current_monitor()` 即可无侵入地记录事件；
- `AgentMonitorWriter` 维护独立异步队列，批量写入 PostgreSQL，队列满时直接丢弃并记错误，不阻塞 Agent；
- 写入失败时采用指数退避有限重试，批量失败会降级为单条重试；
- 序列化器 `serialize_monitor_value` 自动脱敏 `token`、`password`、`secret`、`authorization` 等字段，并截断大文本和大集合；
- 监控记录中的用户标识是运行时快照，不随用户删除而级联清理。

相关代码：`apps/backend/src/echomemory_backend/ai/monitoring/runtime.py`、`apps/backend/src/echomemory_backend/ai/monitoring/writer.py`、`apps/backend/src/echomemory_backend/ai/monitoring/serialization.py`

### 3. 用户画像的异步 judge-update 流程

用户画像不是每次对话都盲目更新，而是设计了两阶段小模型流程：

- 每积累 4 条尚未处理的人类消息，触发一次评估；
- 先用轻量模型做 judge，判断本轮对话是否包含值得记录的信息（只输出 `true`/`false`，非法输出最多重试 3 次）；
- 只有 judge 返回 `true` 时，才用模型基于原画像 + 本轮对话生成新的画像文本；
- 使用 PostgreSQL `pg_advisory_xact_lock(user_id)` 保证同一用户跨进程、跨 worker 串行更新；
- 画像长度严格限制在 500 字以内，作为 AI 对话的长期记忆供 `get_personal_music_context` 工具读取。

相关代码：`apps/backend/src/echomemory_backend/services/user_profile_service.py`

### 4. 私人漫游的实时反馈加权推荐

私人漫游是一个状态化的交互式推荐场景：

- 用户每次收藏/不喜欢的反馈被实时写入 Redis 偏好池/不喜欢池，并按 UTC+8 凌晨 4:00 自动过期；
- 候选歌曲按情绪、兴趣、风格、语言、乐器等标签维度加权评分，同时惩罚不喜欢的歌曲（-10）、艺术家（-5）和标签（-1）；
- 评分后取 top 30，用 softmax 转换为概率分布做加权随机选择，保留探索空间；
- 生成新歌时异步调用小模型生成推荐理由，失败静默，不影响主路径；
- 冷启动时直接随机选一首，无需用户历史。

相关代码：`apps/backend/src/echomemory_backend/services/roam_service.py`

### 5. 内容审核的异步任务租约模型

内容审核不阻塞用户发布路径，而是通过数据库任务表 + 进程内 Worker 异步消费：

- `claim_pending_tasks` 以租约形式领取任务，设置 `lease_seconds`，避免多 worker 重复处理同一任务；
- 加载被审核内容时使用 `SELECT ... FOR UPDATE`，并校验 `moderation_version`，防止旧任务覆盖用户已修改的新内容；
- 审核失败自动重试，超过次数后标记失败并保留监控记录；
- 审核结果通过 `apply_moderation_decision` 统一应用到评论、说说、歌单、用户资料等不同实体。

相关代码：`apps/backend/src/echomemory_backend/services/content_moderation_worker.py`、`apps/backend/src/echomemory_backend/services/content_moderation_service.py`

### 6. AI 工具注册表的元数据驱动设计

工具不是零散装饰器，而是注册到统一的 `ToolRegistry`，每条工具携带元数据：

- `read_only`：只读工具与写操作工具分离，MUTED / RESTRICTED 用户只能访问只读工具；
- `allow_parallel`：控制一次 tool_calls 中是否允许与其它工具并发执行；
- `max_concurrency`：为单个工具维护 `asyncio.Semaphore`，限制其最大并发；
- `tags`：按能力标签过滤，不同场景可暴露不同工具子集。

LangGraph 的 `chatbot` 节点调用 `registry.resolve_tools(context)` 获取当前上下文允许的工具列表，再绑定到模型。

相关代码：`apps/backend/src/echomemory_backend/ai/tools/registry.py`、`apps/backend/src/echomemory_backend/ai/tools/__init__.py`

### 7. DeepSeek ChatModel 的 LangChain 适配与上下文截断

由于底层使用 DeepSeek 自研 HTTP 客户端，项目没有直接用 LangChain 官方模型，而是实现了 `DeepSeekChatModel`（继承 `BaseChatModel`）：

- 桥接 `_generate` / `_agenerate` / `_astream` / `_stream`，让 LangGraph 可以原生调用；
- 透传 DeepSeek 的 `reasoning_content`，流式场景下单独输出 reasoning chunk；
- `_filter_llm_messages` 在发送给模型前截断上下文，只保留 system message 与最近 `ai_max_context_messages` 条消息；截断时避免切断 `AIMessage.tool_calls` 与对应 `ToolMessage` 的配对。

相关代码：`apps/backend/src/echomemory_backend/ai/langchain/deepseek_chat.py`

---

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL, pgvector, Redis |
| AI / RAG | LangChain, LangGraph, DeepSeek, DashScope text-embedding-v4, langgraph-checkpoint-postgres |
| 前端 | Tauri 2, React 19, TypeScript, Vite, Tailwind CSS 4, Zustand, Framer Motion |
| 测试 | pytest, pytest-asyncio, fakeredis, Vitest, Testing Library |
| 基础设施 | Docker Compose, Nginx, PostgreSQL（pgvector）, Redis |

---

## 目录结构

```text
.
├── apps/
│   ├── backend/          # FastAPI 后端
│   └── frontend/         # Tauri + React 桌面端
├── infra/                # Docker Compose 与 Nginx 配置
├── packages/             # 共享包预留目录
├── .agent/               # 项目文档、决策、API 文档与任务资料
├── logs/                 # 本地运行日志
└── temp/                 # 临时文件
```

更完整的目录说明见 `.agent/directory.md`。

---

## 快速开始

### 前置要求

建议在 Windows 11 上开发。克隆仓库前请准备：

- Git
- Python 3.12+
- `uv`（Python 包管理器）
- Node.js 20+ 与 npm
- Docker Desktop，或本机 PostgreSQL + Redis
- Rust stable toolchain
- Microsoft C++ Build Tools 与 Microsoft Edge WebView2（Tauri 2 在 Windows 开发所需；Windows 11 通常已内置 WebView2）
- 可选：Nginx。如果使用 `npm start` 启动前端开发代理，需要本机能执行 `nginx` 命令

中国大陆网络环境下，包管理器必须使用国内镜像。后端 `pyproject.toml` 已配置阿里云 PyPI 镜像；前端 `package-lock.json` 使用 npmmirror 解析地址。首次安装前建议显式设置：

```powershell
npm config set registry https://registry.npmmirror.com
```

Rust/Cargo 如果下载缓慢，请按团队本机规范配置 Cargo 国内镜像；本仓库暂未提交全局 Cargo mirror 配置。

### 1. 克隆仓库

```powershell
git clone <your-repo-url> echomemory
cd echomemory
```

### 2. 启动数据库与 Redis

推荐直接使用仓库提供的 Docker Compose：

```powershell
cd infra
docker compose up -d
cd ..
```

默认服务：

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Docker 数据库账号/密码/库名：`echomemory`

如果不用 Docker，也可以使用本机 PostgreSQL。需要手动创建数据库，并确保可用扩展包括 `pg_trgm` 与 `vector`（pgvector）：

```sql
CREATE DATABASE echomemory;
CREATE DATABASE echomemory_test;
```

测试库 `echomemory_test` 会被 pytest 清空和重建表结构，只能用于测试。

### 3. 配置并启动后端

```powershell
cd apps/backend
Copy-Item .env.example .env
```

编辑 `.env`。最低限度需要：

```env
DATABASE_URL=postgresql+psycopg2://echomemory:echomemory@localhost:5432/echomemory
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<change-me-to-a-random-string>
```

以下功能需要额外密钥，不配置时相关功能不可用或会在调用时失败：

- 文件上传 / 头像：`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_ENDPOINT`、`OSS_BUCKET_NAME`
- AI 对话 / 内容审核：`DEEPSEEK_API_KEY`
- 联网搜索工具：`IQS_API_KEY`
- RAG 向量生成：`DASHSCOPE_API_KEY`

安装依赖并启动：

```powershell
uv sync --extra dev
uv run start
```

后端监听 `http://127.0.0.1:8000`。启动生命周期会自动执行：

- `alembic upgrade head`
- 初始化 LangGraph Postgres Checkpointer 表
- 检查 Redis 连接
- 初始化字典种子数据
- 启动数据库日志、Agent 监控 writer、内容审核 worker、推荐与热度维护任务

### 4. 配置并启动前端

```powershell
cd apps/frontend
npm install
```

开发环境默认已有 `.env.development`：

```env
VITE_API_BASE_URL=/api/v1
```

浏览器开发：

```powershell
npm run dev
```

Vite 监听 `http://127.0.0.1:5173`，并把 `/api` 代理到 `http://127.0.0.1:8000`。

Tauri 桌面开发：

```powershell
npm run tauri:dev
```

`tauri:dev` 会先运行 `npm run dev:tauri`，自动释放 5173 上残留的 Node/Vite 进程，然后启动 Tauri 窗口。

如果需要通过 Nginx 统一代理前端和 API：

```powershell
npm start
```

该命令会使用 `infra/nginx-dev.conf` 启动 Nginx，监听 `http://localhost`，并在 Vite 退出后尝试停止 Nginx。

---

## 开发指南

### 常用命令

#### 后端

```powershell
cd apps/backend
uv sync --extra dev          # 安装依赖
uv run start                 # 启动开发服务器（带热重载）
uv run alembic upgrade head  # 手动执行数据库迁移
uv run pytest                # 运行测试
uv run python scripts/export_openapi.py          # 导出 API 文档
uv run python scripts/generate_error_code_doc.py # 生成错误码文档
```

说明：

- API 文档导出到 `.agent/api-documentations/`。
- FastAPI 应用关闭了运行时 `/docs`、`/redoc` 和 `/openapi.json` 路由；需要文档时使用导出脚本。
- 后端测试默认使用 `echomemory_test` 数据库，运行前请确认该库存在且不是生产数据。

#### 前端

```powershell
cd apps/frontend
npm install        # 安装依赖
npm run dev        # 浏览器开发
npm run tauri:dev  # Tauri 桌面开发
npm run lint       # TypeScript 检查 + ESLint
npm test           # 运行测试
npm run build      # 生产构建（含 TS 检查）
npm run tauri:build # 打包 Tauri 应用
```

说明：

- `npm run build` 会执行 TypeScript 检查并构建 Vite 产物。
- `npm run tauri:build` 会先执行前端构建，再打包 Tauri 应用。
- 生产构建前必须设置 `.env.production` 中的 `VITE_API_BASE_URL`，例如 `https://api.example.com/api/v1`。

### 端口与服务

| 服务 | 默认地址 | 来源 |
| --- | --- | --- |
| 后端 API | `http://127.0.0.1:8000/api/v1` | `apps/backend/src/echomemory_backend/cli.py` |
| Vite | `http://127.0.0.1:5173` | `apps/frontend/vite.config.ts` |
| 开发 Nginx | `http://localhost` | `infra/nginx-dev.conf` |
| PostgreSQL | `localhost:5432` | `infra/docker-compose.yml` |
| Redis | `localhost:6379` | `infra/docker-compose.yml` |

---

## 测试

### 后端测试

后端测试会：

- 从 `.env` 读取共享凭据；
- 将 `DATABASE_URL` 自动改写到 `echomemory_test`；
- 清理测试库中的业务表；
- 使用 FakeRedis 和模拟 DeepSeek 客户端，避免测试调用真实 Redis/LLM。

```powershell
cd apps/backend
uv run pytest
```

### 前端测试

```powershell
cd apps/frontend
npm test
```

---

## 故障排查

| 现象 | 排查方向 |
| --- | --- |
| `Settings` 校验失败 | 检查 `.env` 是否存在，以及 `DATABASE_URL`、`SECRET_KEY` 是否已配置 |
| 后端启动时报 Redis 连接失败 | 确认 Redis 已启动并监听 `6379`，或修正 `REDIS_URL` |
| Alembic 迁移失败 | 确认数据库存在，账号有建表和创建扩展权限，并已安装 pgvector |
| Vite 端口占用 | `npm run tauri:dev` 会自动释放 5173 上的 Node 进程；普通 `npm run dev` 不会 |
| Tauri 编译失败 | 确认已安装 Rust stable、Microsoft C++ Build Tools、Windows SDK 和 WebView2。若要打 MSI，Tauri 2 官方文档还要求启用 Windows VBSCRIPT 可选功能 |
| 生产 Tauri 构建连接不到 API | 检查 `.env.production` 的 `VITE_API_BASE_URL` |

---

## 相关文档

- 项目目录结构：`.agent/directory.md`
- 长期决策记录：`.agent/decision.md`
- API 文档输出目录：`.agent/api-documentations/`
- 后端环境变量示例：`apps/backend/.env.example`
- 前端环境变量：`apps/frontend/.env.development`、`apps/frontend/.env.production`
- Tauri 2 Windows 前置依赖：<https://v2.tauri.app/start/prerequisites/>

---

## 如何贡献

1. **阅读项目约定**：在提交改动前，请先阅读 `.agent/decision.md`，确认你的改动不会违反用户确认过的长期决策。
2. **从 issue 或计划开始**：如果是较大的功能或重构，建议先在 `.agent/plans/` 中留下计划，或在 issue 中讨论范围。
3. **保持最小改动**：只修改与目标相关的文件和模块，避免顺带格式化、重命名或引入无关依赖。
4. **遵循现有代码风格**：
   - 后端：类型注解、Pydantic Schema、SQLAlchemy ORM、Service 层封装；
   - 前端：TypeScript 严格模式、Tailwind CSS、Zustand 状态管理。
5. **补充或更新测试**：修改行为时确保有相关测试覆盖；修复 bug 时先写复现测试。
6. **更新文档**：如果改动涉及目录结构、API 契约、环境变量或构建方式，请同步更新本 README 及 `.agent/` 下的相关文档。
7. **提交前自检**：
   - 后端：`uv run pytest` 通过；
   - 前端：`npm run lint` 与 `npm test` 通过；
   - 不提交 `.env`、`.venv`、`node_modules`、`target`、`logs`、`temp` 等文件。

---

> 本项目仍在活跃开发中，部分功能（如推荐算法）处于早期阶段。如果你发现文档与代码不一致，请以代码和测试为准，并欢迎提交 issue 或 PR。
