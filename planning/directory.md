# 项目目录结构

```
.
├── AGENTS.md
├── planning/
│   ├── 需求.md
│   ├── directory.md
│   ├── for-backend/
│   ├── for-frontend/
│   ├── plans/
│   ├── pngs/
│   ├── searchresults/
│   ├── sql/
│   └── api-documentations/
├── apps/
│   ├── backend/
│   │   ├── .venv/                  # Python 虚拟环境
│   │   ├── pyproject.toml
│   │   ├── .gitignore
│   │   ├── alembic/
│   │   │   ├── alembic.ini
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   ├── src/
│   │   │   └── echomemory_backend/
│   │   │       ├── __init__.py
│   │   │       ├── main.py         # FastAPI 应用入口
│   │   │       ├── core/
│   │   │       │   ├── __init__.py
│   │   │       │   └── config.py   # Pydantic Settings 配置占位
│   │   │       ├── api/
│   │   │       │   ├── __init__.py
│   │   │       │   ├── deps.py     # 依赖注入占位
│   │   │       │   └── v1/
│   │   │       │       ├── __init__.py
│   │   │       │       └── router.py # APIRouter 占位
│   │   │       ├── models/         # ORM 模型占位
│   │   │       ├── schemas/        # Pydantic Schema 占位
│   │   │       ├── services/       # 业务逻辑占位
│   │   │       └── db/
│   │   │           ├── __init__.py
│   │   │           └── session.py  # 数据库 Session 占位
│   │   └── tests/
│   └── frontend/                   # Tauri 2.x + React 19 + TS + Vite + Tailwind CSS
│       ├── package.json
│       ├── vite.config.ts
│       ├── tsconfig.json
│       ├── tsconfig.node.json
│       ├── index.html
│       ├── src/
│       │   ├── main.tsx            # React 应用入口
│       │   ├── App.tsx             # 根组件
│       │   ├── index.css           # 全局样式（Tailwind v4）
│       │   ├── shared/
│       │   │   ├── api/            # 用户 API client 与类型
│       │   │   └── auth/           # token store
│       │   └── test/               # 前端测试 setup
│       └── src-tauri/
│           ├── Cargo.toml          # Rust 项目配置
│           ├── tauri.conf.json     # Tauri 应用配置
│           ├── capabilities/       # 权限配置
│           └── src/
│               ├── main.rs         # Rust 入口
│               └── lib.rs          # Rust 库入口
├── infra/
│   ├── docker-compose.yml          # Postgres (pgvector) + Redis
│   └── .env.example
├── packages/                       # 共享包（预留）
└── shared/                         # 共享资源（预留）
```
