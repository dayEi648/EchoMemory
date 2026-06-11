# AGENTS.md - project

## 1. 项目章程

### 1.1 基本信息

- **项目名称**: echomemory（回声记忆）
- **项目简介**: 围绕 AI Agent 的本地桌面客户端 + 云端 API 音乐平台。当前阶段仅构建 Windows 桌面端。

### 1.2 技术栈

<techstack>

| 层级     | 组件                                                                                                 |
| -------- | ---------------------------------------------------------------------------------------------------- |
| backend  | Python, FastAPI, Alembic, Pydantic, PostgreSQL（含 pgvector）, Redis, LangChain, LangGraph, RAG, OSS |
| frontend | Tauri 2.x, React 19, TypeScript, Vite, Tailwind CSS                                                  |

</techstack>

---

## 2. 工作规则

<workrules>

1. Thinking and Communication
	- Clearly state your assumptions, rather than making silent guesses.
	- When encountering doubts, uncertainties, or information gaps, you must ask questions.
	- If there are multiple interpretations, present all of them - do not silently choose one.
	- When encountering ambiguity: immediately pause, mark the problem and ask questions. 
2. Scope and Design Decisions
	- Before proposing a repair solution, assess whether this solution is the best option, whether it can truly solve the problem, and ensure that it does not introduce regression issues.
	- Do not build beyond the requirements scope.
	- Prohibit speculative design or abstraction.
	- When unsure how to proceed with development, consider how senior engineers or official documentation would solve the problem. You can search online to confirm.
	- Avoid reinventing the wheel. If there is a reliable dependency that can reduce 200 lines of code to just a few lines, use it first.
	- If you find isolated code that already exists, inform the user; do not delete it on your own. 
3. Good Work Habits
	- It is necessary to use the SKILL that is useful for the current task, even if it has only 1% relevance to the current task.
	- It is necessary to use the Tool that is useful for the current work.
	- All code that is not written according to the specifications and operations that are not carried out as required will not be recognized. Therefore, you must strictly abide by various development specifications and work requirements.
	- The project requirement analysis and key decisions are recorded in @planning/决策.md. During the development process, you must not violate the decisions described therein. During the development process, once the user clarifies new design directions, architecture decisions, specification conventions, etc., you must actively record them in `决策.md` using concise language. Before recording, you must obtain the user's consent.
	- 
	</workrules>

---

## 3. 上下文检索索引

根据当前任务按需访问项目资源：

<index>

| Resource            | Path                           | Purpose                              | When to Use                                                  |
| ------------------- | ------------------------------ | ------------------------------------ | ------------------------------------------------------------ |
| Project Charter     | `planning/决策.md`             | 项目旨在达成的目标、已经明确的决策。 | 始终，在启动任何开发之前。                                   |
| Task Plans          | `planning/plans/`              | 任务列表、计划与排期。               | 将复杂的、长期的或者暂时不执行的计划存放在该目录下。         |
| Directory Structure | `planning/directory.md`        | 项目目录结构。                       | 需要了解项目目录结构时，查看此文档。如果项目结构发生变更，需要更新此文档。 |
| Frontend References | `planning/for-frontend/`       | 前端设计指导。                       | 当你需要了解前端设计、样式或其他前端相关决策时，查看此文件夹下有无文档。 |
| Backend References  | `planning/for-backend/`        | 后端设计指导。                       | 当你需要了解后端设计或其他后端相关决策时，查看此文件夹下有无文档。 |
| Database Schema     | `planning/sql/`                | 数据库中的表结构、关系等等。         | 数据库 schema，用于了解该项目的数据库设计；在当前项目中，数据库结构主要由Alembic生成和迁移，应以后端中的ORM模型为准。 |
| Temporary Images    | `planning/pngs/`               | 临时图片资源的存储与清理。           | 将临时图片资源存放在此文档，使用完毕后清理它们。             |
| Search Results      | `planning/searchresults/`      | 搜索操作的结果。                     | 进行联网搜索后，将搜索结果整理并写入该目录下；不删除。已有的搜索结果可能对你的任务有所帮助。 |
| API Documentations  | `planning/api-documentations/` | API 文档。                           | 当你需要了解 API 文档时查看此目录。当前项目的API文档由OpenAPI自动生成。 |

</index>
