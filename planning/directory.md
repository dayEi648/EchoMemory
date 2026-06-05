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
│   └── backend/
│       ├── .venv/                  # Python 虚拟环境
│       ├── pyproject.toml
│       ├── .gitignore
│       ├── alembic/
│       │   ├── alembic.ini
│       │   ├── env.py
│       │   ├── script.py.mako
│       │   └── versions/
│       ├── src/
│       │   └── echomemory_backend/
│       │       ├── __init__.py
│       │       ├── main.py         # FastAPI 应用入口
│       │       ├── core/
│       │       │   ├── __init__.py
│       │       │   └── config.py   # Pydantic Settings 配置占位
│       │       ├── api/
│       │       │   ├── __init__.py
│       │       │   ├── deps.py     # 依赖注入占位
│       │       │   └── v1/
│       │       │       ├── __init__.py
│       │       │       └── router.py # APIRouter 占位
│       │       ├── models/         # ORM 模型占位
│       │       ├── schemas/        # Pydantic Schema 占位
│       │       ├── services/       # 业务逻辑占位
│       │       └── db/
│       │           ├── __init__.py
│       │           └── session.py  # 数据库 Session 占位
│       └── tests/
├── infra/
│   ├── docker-compose.yml          # Postgres (pgvector) + Redis
│   └── .env.example
├── packages/                       # 共享包（预留）
└── shared/                         # 共享资源（预留）
```
