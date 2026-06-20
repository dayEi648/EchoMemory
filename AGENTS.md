# AGENTS.md - project

## 1. 项目章程

### 1.1 基本信息

- **项目名称**: echomemory（回声记忆）
- **项目简介**: 围绕 AI Agent 的本地桌面客户端 + 云端 API 音乐平台。 Windows 桌面端为主要构建方向。

### 1.2 技术栈

<techstack>

| 层级     | 组件                                                                                                 |
| -------- | ---------------------------------------------------------------------------------------------------- |
| backend  | Python, FastAPI, Alembic, Pydantic, PostgreSQL（含 pgvector）, Redis, LangChain, LangGraph, RAG, OSS |
| frontend | Tauri 2.x, React 19, TypeScript, Vite, Tailwind CSS                                                  |

</techstack>

---

## 2. 上下文检索索引

根据当前任务按需访问项目资源：

<index>

| Resource            | Path                           | Purpose                      | When to Use                                                  |
| ------------------- | ------------------------------ | ---------------------------- | ------------------------------------------------------------ |
| Task Plans          | `planning/plans/`              | 任务列表、计划与排期。       | 将复杂的、长期的或者暂时不执行的计划存放在该目录下。         |
| Project Decisions   | `planning/decision.md`         | 用户确认的反直觉长期决策。   | 开发前主动快速查看；当准备修改某个看似异常、非常规或像历史包袱的实现时，必须先确认本文档是否已有约束；用户明确确认了某种反直觉的长期决策新增、变更或废弃时，才维护更新。 |
| Directory Structure | `planning/directory.md`        | 项目目录结构。               | 需要了解项目目录结构时，查看此文档。如果项目结构发生变更，需要更新此文档。 |
| Frontend References | `planning/for-frontend/`       | 前端设计指导。               | 当你需要了解前端设计、样式或其他前端相关决策时，查看此文件夹下有无文档。 |
| Backend References  | `planning/for-backend/`        | 后端设计指导。               | 当你需要了解后端设计或其他后端相关决策时，查看此文件夹下有无文档。 |
| Database Schema     | `planning/sql/`                | 数据库中的表结构、关系等等。 | 数据库 schema，用于了解该项目的数据库设计；在当前项目中，数据库结构主要由Alembic生成和迁移，应以后端中的ORM模型为准。 |
| Temporary Images    | `planning/pngs/`               | 临时图片资源的存储与清理。   | 将临时图片资源存放在此文档，使用完毕后清理它们。             |
| Search Results      | `planning/searchresults/`      | 搜索操作的结果。             | 进行联网搜索后，将搜索结果整理并写入该目录下；不删除。已有的搜索结果可能对你的任务有所帮助。 |
| API Documentations  | `planning/api-documentations/` | API 文档。                   | 当你需要了解 API 文档时查看此目录。                          |

</index>
