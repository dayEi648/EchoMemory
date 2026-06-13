# 项目目录结构

```
.
├── AGENTS.md
├── planning/
│   ├── 需求.md                     # 项目需求与决策记录
│   ├── directory.md                # 本文档：项目目录结构
│   ├── for-backend/                # 后端设计参考文档
│   ├── for-frontend/               # 前端设计参考文档
│   ├── plans/                      # 任务计划与排期
│   ├── pngs/                       # 临时图片资源
│   ├── searchresults/              # 临时搜索结果
│   ├── sql/                        # 数据库 schema、迁移与种子数据
│   └── api-documentations/         # API 文档
├── apps/
│   ├── backend/                    # Python FastAPI 后端
│   │   ├── .venv/                  # Python 虚拟环境
│   │   ├── pyproject.toml
│   │   ├── .gitignore
│   │   ├── alembic/                # Alembic 数据库迁移
│   │   │   ├── alembic.ini
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/           # 迁移脚本
│   │   ├── src/
│   │   │   └── echomemory_backend/
│   │   │       ├── __init__.py
│   │   │       ├── main.py         # FastAPI 应用入口（含 lifespan、全局异常处理器）
│   │   │       ├── core/           # 核心工具与配置
│   │   │       │   ├── __init__.py
│   │   │       │   ├── config.py   # Pydantic Settings 配置
│   │   │       │   ├── exceptions.py   # BusinessError 业务异常定义
│   │   │       │   ├── image_utils.py  # 图片压缩与格式转换
│   │   │       │   ├── oss_client.py   # 阿里云 OSS 异步客户端封装
│   │   │       │   ├── redis_client.py # Redis 异步客户端
│   │   │       │   ├── security.py     # JWT、密码哈希等安全工具
│   │   │       │   └── utils.py        # 通用工具（如 ISO 8601 duration 解析）
│   │   │       ├── api/            # API 层
│   │   │       │   ├── __init__.py
│   │   │       │   ├── deps.py     # FastAPI 依赖注入（SessionDep、CurrentUser 等）
│   │   │       │   └── v1/
│   │   │       │       ├── __init__.py
│   │   │       │       ├── router.py   # v1 路由聚合
│   │   │       │       └── endpoints/  # 业务路由端点
│   │   │       │           ├── __init__.py
│   │   │       │           ├── album.py
│   │   │       │           ├── auth.py
│   │   │       │           ├── collection.py
│   │   │       │           ├── comment.py
│   │   │       │           ├── dictionary.py
│   │   │       │           ├── music.py
│   │   │       │           ├── play_history.py
│   │   │       │           ├── playlist.py
│   │   │       │           ├── space_post.py
│   │   │       │           └── users.py
│   │   │       ├── models/         # SQLAlchemy ORM 模型
│   │   │       │   ├── __init__.py
│   │   │       │   ├── album.py
│   │   │       │   ├── collection.py
│   │   │       │   ├── comment.py
│   │   │       │   ├── dictionary.py
│   │   │       │   ├── enums.py
│   │   │       │   ├── music.py
│   │   │       │   ├── play_history.py
│   │   │       │   ├── playlist.py
│   │   │       │   ├── space_post.py
│   │   │       │   ├── user.py
│   │   │       │   ├── user_tag.py
│   │   │       │   └── vector_document.py  # RAG 向量文档模型
│   │   │       ├── schemas/        # Pydantic Schema（请求/响应模型）
│   │   │       │   ├── __init__.py
│   │   │       │   ├── album.py
│   │   │       │   ├── collection.py
│   │   │       │   ├── comment.py
│   │   │       │   ├── dictionary.py
│   │   │       │   ├── music.py
│   │   │       │   ├── play_history.py
│   │   │       │   ├── playlist.py
│   │   │       │   ├── space_post.py
│   │   │       │   ├── user.py
│   │   │       │   └── user_tag.py
│   │   │       ├── services/       # 业务逻辑服务层
│   │   │       │   ├── __init__.py
│   │   │       │   ├── admin_service.py
│   │   │       │   ├── album_service.py
│   │   │       │   ├── auth_service.py
│   │   │       │   ├── collection_service.py
│   │   │       │   ├── comment_service.py
│   │   │       │   ├── dictionary_service.py
│   │   │       │   ├── music_service.py
│   │   │       │   ├── play_history_service.py
│   │   │       │   ├── playlist_service.py
│   │   │       │   ├── space_post_service.py
│   │   │       │   ├── user_service.py
│   │   │       │   └── user_tag_service.py
│   │   │       ├── rag/            # RAG 基础设施
│   │   │       │   ├── __init__.py
│   │   │       │   ├── embeddings.py     # text-embedding-v4 客户端封装
│   │   │       │   └── vector_store.py   # pgvector 向量存储封装
│   │   │       └── db/             # 数据库连接与会话管理
│   │   │           ├── __init__.py
│   │   │           ├── base.py     # SQLAlchemy Base 与模型导入
│   │   │           └── session.py  # 异步/同步引擎与 SessionLocal
│   │   └── tests/                  # pytest 测试
│   │       ├── __init__.py
│   │       ├── conftest.py         # 测试夹具（数据库、FakeRedis、TestClient）
│   │       ├── test_album.py
│   │       ├── test_auth.py
│   │       ├── test_collection.py
│   │       ├── test_comment.py
│   │       ├── test_dictionary.py
│   │       ├── test_music.py
│   │       ├── test_play_history.py
│   │       ├── test_playlist.py
│   │       ├── test_redis_client.py
│   │       ├── test_security.py
│   │       ├── test_space_post.py
│   │       ├── test_user_tag.py
│   │       ├── test_users.py
│   │       ├── test_embeddings.py  # Embedding 客户端测试
│   │       └── test_vector_store.py # 向量存储测试
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
│       │   ├── index.css           # 全局样式（Tailwind v4）
│       │   ├── shared/             # 共享模块
│       │   │   ├── api/            # API client 与类型定义
│       │   │   │   ├── types.ts
│       │   │   │   └── userApi.ts
│       │   │   └── auth/           # Token 状态管理
│       │   │       └── tokenStore.ts
│       │   └── test/               # 前端测试 setup
│       │       └── setup.ts
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
└── shared/                         # 共享资源（预留）
```
