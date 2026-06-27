# echomemory（回声记忆）

echomemory 是一个围绕 AI Agent 的音乐平台项目，当前重点是 Windows 桌面端。本仓库采用 monorepo 结构，包含：

- 后端：FastAPI API 服务，负责用户、音乐、专辑、歌单、评论、通知、私信、推荐、管理后台、AI 对话、内容审核、RAG 与 Agent 监控。
- 前端：Tauri 2 + React 19 + TypeScript 桌面客户端，开发态由 Vite 提供页面服务。
- 基础设施：PostgreSQL（含 pgvector 扩展）、Redis、Nginx 示例配置。

> 本仓库是开发环境配置，不是生产环境配置。不要把本地 `.env`、密钥、数据库密码或 OSS/LLM API Key 提交到仓库。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic, PostgreSQL, pgvector, Redis, LangChain, LangGraph |
| 前端 | Tauri 2, React 19, TypeScript, Vite, Tailwind CSS |
| AI / RAG | DeepSeek, 阿里云 IQS Search MCP, DashScope text-embedding-v4, LangGraph Postgres Checkpointer |
| 测试 | pytest, pytest-asyncio, fakeredis, Vitest, Testing Library |

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

## 前置要求

建议在 Windows 11 上开发。克隆仓库前请准备：

- Git
- Python 3.12+
- `uv`
- Node.js 20+ 与 npm
- Docker Desktop，或本机 PostgreSQL + Redis
- Rust stable toolchain
- Microsoft C++ Build Tools 与 Microsoft Edge WebView2（Tauri 2 在 Windows 开发所需；Windows 11 通常已内置 WebView2）
- 可选：Nginx。如果使用 `npm start` 启动前端开发代理，需要本机能执行 `nginx` 命令。

中国大陆网络环境下，包管理器必须使用国内镜像。后端 `pyproject.toml` 已配置阿里云 PyPI 镜像；前端 `package-lock.json` 使用 npmmirror 解析地址。首次安装前建议显式设置：

```powershell
npm config set registry https://registry.npmmirror.com
```

Rust/Cargo 如果下载缓慢，请按团队本机规范配置 Cargo 国内镜像；本仓库暂未提交全局 Cargo mirror 配置。

## 克隆与初始化

```powershell
git clone <your-repo-url> echomemory
cd echomemory
```

### 1. 启动数据库与 Redis

推荐直接使用仓库提供的 Docker Compose：

```powershell
cd infra
docker compose up -d
cd ..
```

默认服务：

- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Docker 数据库账号：`echomemory`
- Docker 数据库密码：`echomemory`
- Docker 数据库名：`echomemory`

如果不用 Docker，也可以使用本机 PostgreSQL。需要手动创建数据库，并确保可用扩展包括：

- `pg_trgm`
- `vector`（pgvector）

本机开发示例：

```sql
CREATE DATABASE echomemory;
CREATE DATABASE echomemory_test;
```

测试库 `echomemory_test` 会被 pytest 清空和重建表结构，只能用于测试。

### 2. 配置后端环境变量

```powershell
cd apps/backend
Copy-Item .env.example .env
```

编辑 `apps/backend/.env`。最低限度需要：

```env
DATABASE_URL=postgresql+psycopg2://echomemory:echomemory@localhost:5432/echomemory
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<change-me-to-a-random-string>
```

如果你使用本机默认 PostgreSQL 用户，可改为：

```env
DATABASE_URL=postgresql+psycopg2://postgres:<your-password>@localhost:5432/echomemory
```

以下功能需要额外密钥，不配置时相关功能不可用或会在调用时失败：

- 文件上传 / 头像：`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_ENDPOINT`、`OSS_BUCKET_NAME`
- AI 对话 / 内容审核：`DEEPSEEK_API_KEY`
- 联网搜索工具：`IQS_API_KEY`
- RAG 向量生成：`DASHSCOPE_API_KEY`

### 3. 安装后端依赖

```powershell
cd apps/backend
uv sync --extra dev
```

启动后端：

```powershell
uv run start
```

后端监听 `http://127.0.0.1:8000`。启动生命周期会自动执行：

- `alembic upgrade head`
- 初始化 LangGraph Postgres Checkpointer 表
- 检查 Redis 连接
- 初始化字典种子数据
- 启动数据库日志、Agent 监控 writer、内容审核 worker、推荐与热度维护任务

也可以手动执行迁移：

```powershell
cd apps/backend
uv run alembic upgrade head
```

### 4. 配置并启动前端

```powershell
cd apps/frontend
npm install
```

开发环境默认已有 `apps/frontend/.env.development`：

```env
VITE_API_BASE_URL=/api/v1
```

普通浏览器开发：

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

## 常用命令

### 后端

```powershell
cd apps/backend
uv sync --extra dev
uv run start
uv run alembic upgrade head
uv run pytest
uv run python scripts/export_openapi.py
uv run python scripts/generate_error_code_doc.py
```

说明：

- API 文档导出到 `.agent/api-documentations/`。
- FastAPI 应用关闭了运行时 `/docs`、`/redoc` 和 `/openapi.json` 路由；需要文档时使用导出脚本。
- 后端测试默认使用 `echomemory_test` 数据库，运行前请确认该库存在且不是生产数据。

### 前端

```powershell
cd apps/frontend
npm install
npm run dev
npm run tauri:dev
npm run lint
npm test
npm run build
npm run tauri:build
```

说明：

- `npm run build` 会执行 TypeScript 检查并构建 Vite 产物。
- `npm run tauri:build` 会先执行前端构建，再打包 Tauri 应用。
- 生产构建前必须设置 `apps/frontend/.env.production` 中的 `VITE_API_BASE_URL`，例如 `https://api.example.com/api/v1`。

## 端口与服务

| 服务 | 默认地址 | 来源 |
| --- | --- | --- |
| 后端 API | `http://127.0.0.1:8000/api/v1` | `apps/backend/src/echomemory_backend/cli.py` |
| Vite | `http://127.0.0.1:5173` | `apps/frontend/vite.config.ts` |
| 开发 Nginx | `http://localhost` | `infra/nginx-dev.conf` |
| PostgreSQL | `localhost:5432` | `infra/docker-compose.yml` |
| Redis | `localhost:6379` | `infra/docker-compose.yml` |

## 重要开发约定

- 后端统一响应信封为 `{ code, msg, data }`，前端应使用错误码判断业务错误，不要依赖 `msg` 字符串。
- Alembic 迁移读取 `apps/backend/.env` 中的 `DATABASE_URL`。
- 数据库需要 PostgreSQL 扩展 `pg_trgm` 与 `vector`。Docker 镜像已包含 pgvector；本机数据库需自行安装 pgvector。
- `apps/backend/.env`、`apps/frontend/node_modules/`、`apps/backend/.venv/`、Tauri `target/`、`logs/`、`temp/` 都不应提交。
- `.agent/decision.md` 记录了用户确认过的长期反直觉决策，修改相关业务前应先阅读。
- `.agent/api-documentations/` 存放导出的 API 文档；生成脚本会覆盖同名文件。

## 测试注意事项

后端测试会：

- 从 `apps/backend/.env` 读取共享凭据；
- 将 `DATABASE_URL` 自动改写到 `echomemory_test`；
- 清理测试库中的业务表；
- 使用 FakeRedis 和模拟 DeepSeek 客户端，避免测试调用真实 Redis/LLM。

因此运行后端测试前至少要有可连接的 PostgreSQL 测试库：

```powershell
cd apps/backend
uv run pytest
```

前端测试：

```powershell
cd apps/frontend
npm test
```

## 故障排查

- `Settings` 校验失败：检查 `apps/backend/.env` 是否存在，以及 `DATABASE_URL`、`SECRET_KEY` 是否已配置。
- 后端启动时报 Redis 连接失败：确认 Redis 已启动并监听 `6379`，或修正 `REDIS_URL`。
- Alembic 迁移失败：确认数据库存在，账号有建表和创建扩展权限，并已安装 pgvector。
- Vite 端口占用：`npm run tauri:dev` 会自动释放 5173 上的 Node 进程；普通 `npm run dev` 不会。
- Tauri 编译失败：确认已安装 Rust stable、Microsoft C++ Build Tools、Windows SDK 和 WebView2。若要打 MSI，Tauri 2 官方文档还要求启用 Windows VBSCRIPT 可选功能。
- 生产 Tauri 构建连接不到 API：检查 `apps/frontend/.env.production` 的 `VITE_API_BASE_URL`。

## 相关文档

- 项目目录结构：`.agent/directory.md`
- 长期决策记录：`.agent/decision.md`
- API 文档输出目录：`.agent/api-documentations/`
- 后端环境变量示例：`apps/backend/.env.example`
- 前端环境变量：`apps/frontend/.env.development`、`apps/frontend/.env.production`
- Tauri 2 Windows 前置依赖：<https://v2.tauri.app/start/prerequisites/>
