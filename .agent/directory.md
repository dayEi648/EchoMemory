# 项目目录结构

```
.
├── AGENTS.md
├── CLAUDE.md
├── .agent/                         # Agent 文档与资料
│   ├── decision.md                 # 用户确认的反直觉长期决策
│   ├── directory.md                # 本文档：项目目录结构
│   ├── for-backend/                # 后端设计参考文档
│   ├── for-frontend/               # 前端设计参考文档
│   ├── plans/                      # 任务计划与排期
│   ├── searchresults/              # 临时搜索结果
│   └── api-documentations/         # API 文档
├── apps/
│   ├── backend/                    # Python FastAPI 后端
│   │   ├── .venv/                  # Python 虚拟环境
│   │   ├── pyproject.toml
│   │   ├── .gitignore
│   │   ├── alembic.ini             # Alembic 配置文件
│   │   ├── alembic/                # Alembic 数据库迁移
│   │   ├── scripts/                # 开发辅助脚本
│   │   ├── src/
│   │   │   └── echomemory_backend/
│   │   │       ├── __init__.py
│   │   │       ├── cli.py          # 命令行入口
│   │   │       ├── main.py         # FastAPI 应用入口
│   │   │       ├── data/           # 运行时数据与种子文件
│   │   │       ├── core/           # 核心工具与配置
│   │   │       │   ├── config.py   # Pydantic Settings 配置
│   │   │       │   ├── cache/      # 业务缓存
│   │   │       │   ├── clients/    # 外部服务客户端
│   │   │       │   ├── exceptions/ # 异常与全局处理器
│   │   │       │   ├── inbox/      # 私信/通知 Pub/Sub
│   │   │       │   ├── logging/    # 数据库日志持久化
│   │   │       │   ├── security/   # 安全工具
│   │   │       │   └── utils/      # 通用工具
│   │   │       ├── ai/             # AI 基础设施
│   │   │       │   ├── clients/    # 底层 LLM HTTP 客户端
│   │   │       │   ├── langchain/  # LangChain 兼容模型/适配器
│   │   │       │   ├── tools/      # 跨 Graph/Chain 复用的工具
│   │   │       │   ├── graphs/     # LangGraph 工作流
│   │   │       │   │   ├── content_moderation/  # 评论/说说自动审核工作流
│   │   │       │   │   └── conversation/        # AI 对话工作流
│   │   │       │   └── monitoring/ # Agent 监控采集基础设施
│   │   │       ├── api/            # API 层
│   │   │       │   ├── deps.py     # FastAPI 依赖注入
│   │   │       │   ├── envelope_middleware.py   # 统一响应信封中间件
│   │   │       │   ├── helpers.py               # API 辅助函数
│   │   │       │   └── v1/
│   │   │       │       ├── router.py            # v1 路由聚合
│   │   │       │       └── endpoints/           # 业务路由端点
│   │   │       ├── models/         # SQLAlchemy ORM 模型
│   │   │       ├── schemas/        # Pydantic Schema
│   │   │       ├── services/       # 业务逻辑服务层
│   │   │       ├── rag/            # RAG 基础设施
│   │   │       └── db/             # 数据库连接与会话管理
│   │   └── tests/                  # pytest 测试
│   └── frontend/                   # Tauri 2.x + React 19 + TS + Vite + Tailwind CSS
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── tsconfig.node.json
│       ├── index.html
│       ├── src/
│       │   ├── main.tsx            # React 应用入口
│       │   ├── App.tsx             # 根组件
│       │   ├── App.test.tsx        # 根组件测试
│       │   ├── index.css           # 全局样式
│       │   ├── components/         # 组件目录
│       │   │   ├── ai/             # AI 对话结构化卡片组件
│       │   │   ├── layout/         # 布局组件
│       │   │   ├── motion/         # 动画/过渡组件
│       │   │   ├── player/         # 播放器相关组件
│       │   │   └── ui/             # 通用 UI 组件
│       │   ├── shared/             # 共享模块
│       │   │   ├── api/            # API client 与类型定义
│       │   │   ├── auth/           # Token 状态管理
│       │   │   ├── constants/      # 全局常量
│       │   │   └── stores/         # 全局状态管理
│       │   ├── pages/              # 页面组件
│       │   │   └── admin/          # 管理后台页面
│       │   └── test/               # 前端测试 setup
│       └── src-tauri/              # Tauri Rust 层
│           ├── Cargo.toml
│           ├── tauri.conf.json
│           ├── capabilities/
│           │   └── default.json
│           └── src/
│               ├── main.rs         # Rust 应用入口
│               └── lib.rs          # Rust 库入口
├── infra/
│   ├── docker-compose.yml          # Postgres (pgvector) + Redis
│   └── .env.example
├── packages/                       # 共享包（预留）
├── logs/                           # 运行日志（Nginx / 应用访问日志等）
└── temp/                           # 临时文件与缓存目录
```
