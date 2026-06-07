# 开发计划：评论模块 — TDD 测试驱动开发

## 目标

为 echomemory 后端实现评论模块的基础 API，支持对音乐、歌单、空间动态发表评论、回复、点赞和点踩。

**关键约束**：
- 仅开发基础 CRUD 接口，不维护反规范化计数（`comment_count`、`reply_count` 等暂不更新，后续由后台任务处理）。
- 严格遵循 TDD：Red → Green → Refactor。
- 评论列表仅返回 root 评论（`parent_id IS NULL`），不展开回复列表。
- 删除为软删除（`is_deleted=True`）。

---

## 接口清单

| 接口 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `POST /api/v1/comments` | 发表评论 | ActiveUser | 支持回复（parent_id） |
| `GET /api/v1/comments/{target_type}/{target_id}` | 获取评论列表 | ActiveUser | 仅 root 评论，分页，时间倒序，排除已删除 |
| `DELETE /api/v1/comments/{comment_id}` | 删除评论 | ActiveUser | 软删除，仅本人可操作 |
| `POST /api/v1/comments/{comment_id}/like` | 点赞评论 | ActiveUser | 幂等 |
| `DELETE /api/v1/comments/{comment_id}/like` | 取消点赞 | ActiveUser | 幂等 |
| `POST /api/v1/comments/{comment_id}/dislike` | 点踩评论 | ActiveUser | 幂等 |
| `DELETE /api/v1/comments/{comment_id}/dislike` | 取消点踩 | ActiveUser | 幂等 |

**target_type** 支持：`music`, `playlist`, `space_post`

---

## TDD 开发顺序

```
Step 1: 编写测试 tests/test_comment.py（覆盖全部 7 个接口 + 边界场景）
Step 2: 运行测试 → 确认全部失败（Red）
Step 3: 编写 schemas/comment.py
Step 4: 编写 services/comment_service.py
Step 5: 编写 api/v1/endpoints/comment.py
Step 6: 注册路由 api/v1/router.py
Step 7: 运行测试 → 确认全部通过（Green）
Step 8: 运行全量回归测试 pytest tests/ -v
```

---

## 新增文件

| 文件 | 用途 |
|------|------|
| `tests/test_comment.py` | TDD 测试（约 30 个用例） |
| `schemas/comment.py` | Comment 相关的 Pydantic Schema |
| `services/comment_service.py` | 评论业务逻辑 |
| `api/v1/endpoints/comment.py` | API 端点 |

## 修改文件

| 文件 | 修改内容 |
|------|----------|
| `api/v1/router.py` | `include_router(comment.router)` |
| `tests/conftest.py` | TRUNCATE 列表追加 `comments, comment_likes, comment_dislikes`（已包含，无需修改） |

---

## 测试覆盖场景

### 发表评论
- 对音乐发表评论 → 201
- 对歌单发表评论 → 201
- 对空间动态发表评论 → 201
- 回复评论 → 201（parent_id 正确，root_id 自动计算）
- 回复一个回复（嵌套回复）→ 201（is_nested_reply=True）
- 无效 target_type → 400
- 目标不存在 → 404
- 未上架音乐 → 404
- 空内容 → 422
- parent_id 不存在 → 404
- parent_id 指向已删除评论 → 404
- 未认证 → 401

### 获取评论列表
- 获取音乐的 root 评论列表 → 200
- 仅返回 root 评论（parent_id IS NULL）
- 已删除评论被排除
- 空列表 → 200，空数组
- 分页 → limit/offset 正确
- 时间倒序
- 未认证 → 401

### 删除评论
- 删除自己的评论 → 204（软删除）
- 删除他人的评论 → 403
- 删除不存在的评论 → 404
- 未认证 → 401

### 点赞 / 点踩
- 点赞成功 → 201，幂等
- 取消点赞 → 204，幂等
- 点踩成功 → 201，幂等
- 取消点踩 → 204，幂等
- 对不存在的评论操作 → 404
- 未认证 → 401

---

## 成功标准

- `pytest tests/test_comment.py -v` 全部通过
- `pytest tests/ -v` 全量回归通过（现有测试不失败）
- 无新增 warnings 或 errors
