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
│   │   │       │   ├── cache/      # 业务缓存
│   │   │       │   │   └── general.py    # 通用 Redis 缓存工具
│   │   │       │   ├── clients/    # 外部服务客户端
│   │   │       │   │   ├── oss_client.py   # 阿里云 OSS 异步客户端封装
│   │   │       │   │   └── redis_client.py # Redis 异步客户端
│   │   │       │   ├── exceptions/ # 异常与全局处理器
│   │   │       │   │   ├── business.py       # BusinessError 业务异常定义
│   │   │       │   │   └── handlers.py       # FastAPI 全局异常处理器
│   │   │       │   ├── inbox/      # 私信/通知 Pub/Sub
│   │   │       │   │   └── pubsub.py
│   │   │       │   ├── security/   # 安全工具
│   │   │       │   │   └── security.py     # JWT、密码哈希等
│   │   │       │   └── utils/      # 通用工具
│   │   │       │       ├── common.py       # 通用工具（如 ISO 8601 duration 解析）
│   │   │       │       ├── image_utils.py  # 图片压缩与格式转换
│   │   │       │       └── seed_data.py    # 字典表种子数据管理
│   │   │       ├── ai/             # AI 基础设施
│   │   │       │   ├── __init__.py
│   │   │       │   ├── clients/            # 底层 LLM HTTP 客户端
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   └── deepseek.py     # DeepSeek 异步/同步客户端
│   │   │       │   ├── langchain/          # LangChain 兼容模型/适配器
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   └── deepseek_chat.py # DeepSeek ChatModel 适配器
│   │   │       │   ├── tools/              # 跨 Graph/Chain 复用的工具
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   └── ...             # 未来：music.py, playlist.py 等
│   │   │       │   └── graphs/             # LangGraph 工作流与共享设施
│   │   │       │       ├── __init__.py
│   │   │       │       ├── checkpointer.py # Postgres Checkpointer 生命周期
│   │   │       │       └── conversation/   # AI 对话工作流
│   │   │       │           ├── __init__.py
│   │   │       │           ├── state.py    # 对话状态定义
│   │   │       │           ├── nodes/      # 普通节点目录
│   │   │       │           │   ├── __init__.py
│   │   │       │           │   └── chatbot.py
│   │   │       │           ├── builder.py  # 状态图构建器
│   │   │       │           ├── cache.py    # 对话 Redis 缓存
│   │   │       │           └── prompts.py  # 对话提示词常量
│   │   │       ├── api/            # API 层
│   │   │       │   ├── __init__.py
│   │   │       │   ├── deps.py     # FastAPI 依赖注入（SessionDep、CurrentUser 等）
│   │   │       │   └── v1/
│   │   │       │       ├── __init__.py
│   │   │       │       ├── router.py   # v1 路由聚合
│   │   │       │       └── endpoints/  # 业务路由端点
│   │   │       │           ├── __init__.py
│   │   │       │           ├── ai_conversation.py  # AI 对话
│   │   │       │           ├── album.py
│   │   │       │           ├── auth.py
│   │   │       │           ├── carousel.py
│   │   │       │           ├── collection.py
│   │   │       │           ├── comment.py
│   │   │       │           ├── dictionary.py
│   │   │       │           ├── message.py
│   │   │       │           ├── music.py
│   │   │       │           ├── notification.py
│   │   │       │           ├── play_history.py
│   │   │       │           ├── playlist.py
│   │   │       │           ├── recommendation.py
│   │   │       │           ├── space_post.py
│   │   │       │           ├── users.py
│   │   │       │           └── ws_inbox.py
│   │   │       ├── models/         # SQLAlchemy ORM 模型
│   │   │       │   ├── __init__.py
│   │   │       │   ├── ai_conversation.py    # AI 对话会话元数据
│   │   │       │   ├── album.py
│   │   │       │   ├── collection.py
│   │   │       │   ├── comment.py
│   │   │       │   ├── dictionary.py
│   │   │       │   ├── enums.py
│   │   │       │   ├── message.py
│   │   │       │   ├── music.py
│   │   │       │   ├── notification.py
│   │   │       │   ├── play_history.py
│   │   │       │   ├── playlist.py
│   │   │       │   ├── recommendation.py
│   │   │       │   ├── space_post.py
│   │   │       │   ├── user.py
│   │   │       │   ├── user_tag.py
│   │   │       │   └── vector_document.py  # RAG 向量文档模型
│   │   │       ├── schemas/        # Pydantic Schema（请求/响应模型）
│   │   │       │   ├── __init__.py
│   │   │       │   ├── ai_conversation.py
│   │   │       │   ├── album.py
│   │   │       │   ├── carousel.py
│   │   │       │   ├── collection.py
│   │   │       │   ├── comment.py
│   │   │       │   ├── dictionary.py
│   │   │       │   ├── message.py
│   │   │       │   ├── music.py
│   │   │       │   ├── notification.py
│   │   │       │   ├── play_history.py
│   │   │       │   ├── playlist.py
│   │   │       │   ├── space_post.py
│   │   │       │   ├── user.py
│   │   │       │   └── user_tag.py
│   │   │       ├── services/       # 业务逻辑服务层
│   │   │       │   ├── __init__.py
│   │   │       │   ├── admin_service.py
│   │   │       │   ├── ai_conversation_service.py
│   │   │       │   ├── album_service.py
│   │   │       │   ├── auth_service.py
│   │   │       │   ├── carousel_service.py
│   │   │       │   ├── collection_service.py
│   │   │       │   ├── comment_service.py
│   │   │       │   ├── dictionary_reference_service.py
│   │   │       │   ├── dictionary_service.py
│   │   │       │   ├── message_service.py
│   │   │       │   ├── music_service.py
│   │   │       │   ├── notification_service.py
│   │   │       │   ├── play_history_service.py
│   │   │       │   ├── playlist_service.py
│   │   │       │   ├── recommendation_service.py
│   │   │       │   ├── space_post_service.py
│   │   │       │   ├── stats_service.py
│   │   │       │   ├── user_service.py
│   │   │       │   ├── user_tag_service.py
│   │   │       │   └── association_helpers.py
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
│   │       ├── test_ai_conversation.py   # AI 对话测试
│   │       ├── test_album.py
│   │       ├── test_auth.py
│   │       ├── test_cache.py
│   │       ├── test_collection.py
│   │       ├── test_comment.py
│   │       ├── test_dictionary.py
│   │       ├── test_embeddings.py  # Embedding 客户端测试
│   │       ├── test_image_utils.py
│   │       ├── test_llm.py
│   │       ├── test_message.py
│   │       ├── test_music.py
│   │       ├── test_notification.py
│   │       ├── test_play_history.py
│   │       ├── test_playlist.py
│   │       ├── test_recommendations.py
│   │       ├── test_redis_client.py
│   │       ├── test_security.py
│   │       ├── test_space_post.py
│   │       ├── test_user_tag.py
│   │       ├── test_users.py
│   │       ├── test_utils.py
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
