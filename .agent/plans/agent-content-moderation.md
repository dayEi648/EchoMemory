# Implementation Plan: Agent 自动内容审核

## Overview

为评论和个人空间说说增加可靠的异步 Agent 审核。内容发表后立即可见；审核计算安全分、推荐分及档位。危险内容自动逻辑删除并通知作者，推荐内容设置 `is_recommended=true`。审核任务连续失败三次后隐藏内容并标记 `FAILED`。管理员可查询全部内容和审核状态，重新审核、人工改档及恢复因审核删除的内容。用户维度统计保存风险、危险、推荐内容数量。

## Architecture Decisions

- 使用 PostgreSQL 持久化 `content_moderation_tasks`，内容创建与任务创建同事务提交。
- Worker 使用 `FOR UPDATE SKIP LOCKED` 领取任务，支持多实例并发和宕机恢复。
- 审核场景复用通用 `agent_runs` / `agent_events`，场景标识为 `content_moderation`。
- 模型只输出结构化候选分值与理由；档位映射和业务动作由代码决定。
- 安全分：0–3 危险、4–6 风险、7–10 安全；推荐分：8–10 推荐。
- 内容发表后立即可见；第三次失败后隐藏并标记审核失败。
- 用户统计按每条内容最新有效审核结果维护。用户主动删除不减少历史统计。
- 审核删除与用户主动删除分开记录，只有审核删除允许管理员恢复。

## Phase 1: Database and Contracts

### Task 1: Add moderation schema

Acceptance criteria:

- 评论和空间动态具有安全分、推荐分、安全档位、推荐档位、审核状态、审核原因、审核时间、删除原因。
- 存在可靠审核任务表、审核历史表和用户统计表。
- 必要的检查约束、唯一约束和管理查询索引完整。

Verification:

- Alembic upgrade succeeds.
- ORM metadata and migration agree.

### Task 2: Define moderation contracts

Acceptance criteria:

- Pydantic validates model scores within 0–10.
- Score-to-level mapping is deterministic and fully tested.
- Admin list and action schemas are explicit and paginated.

Verification:

- Unit tests fail before implementation and pass after implementation.

## Phase 2: Reliable Moderation

### Task 3: Enqueue all supported content

Acceptance criteria:

- New comments, original posts, forwards and forward captions enqueue exactly one task in the same transaction.
- Existing content API behavior remains compatible.

Verification:

- Comment and space-post integration tests.

### Task 4: Execute and monitor moderation

Acceptance criteria:

- Worker claims jobs without duplicate concurrent processing.
- Every attempt creates a monitored `content_moderation` Agent run.
- Successful results update content, history and user statistics atomically.
- Failed attempts retry with backoff; third failure hides content and marks `FAILED`.

Verification:

- Unit tests for claim, retry and result application.
- Agent monitoring tests assert run and event coverage.

### Task 5: Notify dangerous-content authors

Acceptance criteria:

- Dangerous content receives an unread system notification after logical deletion.
- Notification includes content type, content id and reason.

Verification:

- Notification integration test.

## Phase 3: Admin API

### Task 6: Add content administration endpoints

Acceptance criteria:

- Separate paginated endpoints for comments and space posts.
- Filters cover text/user/target, safety level, recommendation level, moderation status, deletion state and time.
- Admin can request re-review, apply manual scores/levels and restore moderation-deleted content.

Verification:

- API tests for authorization, filtering and each action.

## Phase 4: Admin Frontend

### Task 7: Add API client and types

Acceptance criteria:

- Typed client exposes lists, re-review, manual review and restore.

Verification:

- API client tests validate paths and payloads.

### Task 8: Add comment and space-post management pages

Acceptance criteria:

- Both pages provide filters, pagination, status distinction and detail dialogs.
- Actions expose loading/error/success states and are keyboard accessible.
- Admin navigation and routes include both pages.

Verification:

- Vitest component tests.
- TypeScript build succeeds.

## Final Verification

- Backend focused tests and full suite pass.
- Frontend tests, lint and production build pass.
- Two review passes cover data consistency, concurrency, authorization, regression and UI behavior.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Duplicate workers process one content item | Row locking, one active task per content, idempotent result transaction |
| Stale result overwrites newer manual review | Content moderation version checked when applying results |
| Statistics drift | Differential updates under user-stat row lock; reconciliation-friendly history |
| Model returns invalid output | Strict Pydantic validation; retry as failed attempt |
| Monitoring failure blocks moderation | Reuse non-blocking monitor writer per project decision |
| Process crashes with task in PROCESSING | Lease timeout returns stale tasks to retryable state |
