# 开发计划：收藏模块 — TDD 测试驱动开发

## 目标

为 echomemory 后端实现收藏模块的基础 API，覆盖音乐、专辑、歌单三种对象的收藏/取消收藏/列表查询，以及「已发布音乐」标记功能。

**关键约束**：
- 仅开发基础 CRUD 接口，不开发复杂业务（如收藏数自动同步、推荐等）。
- 严格遵循 TDD：Red → Green → Refactor。
- 收藏/取消收藏为幂等操作（重复收藏静默成功，未收藏时取消静默成功）。

---

## 接口清单

| 接口 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `POST /api/v1/collections/musics/{music_id}` | 收藏音乐 | ActiveUser | 幂等：已收藏则静默返回 |
| `DELETE /api/v1/collections/musics/{music_id}` | 取消收藏音乐 | ActiveUser | 幂等：未收藏则静默返回 204 |
| `GET /api/v1/collections/musics` | 我的收藏音乐列表 | ActiveUser | 分页，按收藏时间倒序 |
| `POST /api/v1/collections/albums/{album_id}` | 收藏专辑 | ActiveUser | 同上 |
| `DELETE /api/v1/collections/albums/{album_id}` | 取消收藏专辑 | ActiveUser | 同上 |
| `GET /api/v1/collections/albums` | 我的收藏专辑列表 | ActiveUser | 同上 |
| `POST /api/v1/collections/playlists/{playlist_id}` | 收藏歌单 | ActiveUser | 同上 |
| `DELETE /api/v1/collections/playlists/{playlist_id}` | 取消收藏歌单 | ActiveUser | 同上 |
| `GET /api/v1/collections/playlists` | 我的收藏歌单列表 | ActiveUser | 同上 |
| `POST /api/v1/collections/releases/{music_id}` | 标记已发布音乐 | ActiveUser | 幂等 |
| `DELETE /api/v1/collections/releases/{music_id}` | 取消标记 | ActiveUser | 幂等 |
| `GET /api/v1/collections/releases` | 我的已发布音乐列表 | ActiveUser | 分页，按标记时间倒序 |

---

## TDD 开发顺序

```
Step 1: 编写测试 tests/test_collection.py（覆盖全部 12 个接口 + 边界场景）
Step 2: 运行测试 → 确认全部失败（Red）
Step 3: 编写 schemas/collection.py
Step 4: 编写 services/collection_service.py
Step 5: 编写 api/v1/endpoints/collection.py
Step 6: 注册路由 api/v1/router.py
Step 7: 运行测试 → 确认全部通过（Green）
Step 8: 运行全量回归测试 pytest tests/ -v
```

---

## 新增文件

| 文件 | 用途 |
|------|------|
| `tests/test_collection.py` | TDD 测试（先写，约 25~30 个用例） |
| `schemas/collection.py` | Collection 相关的 Pydantic Schema |
| `services/collection_service.py` | 收藏业务逻辑 |
| `api/v1/endpoints/collection.py` | API 端点 |

## 修改文件

| 文件 | 修改内容 |
|------|----------|
| `api/v1/router.py` | `include_router(collection.router)` |

## 不变更文件

| 文件 | 原因 |
|------|------|
| `tests/conftest.py` | TRUNCATE 列表已包含 4 张收藏表，无需修改 |

---

## 测试覆盖场景

### 音乐收藏
- 成功收藏音乐 → 201
- 重复收藏同一音乐 → 201（幂等）
- 收藏不存在的音乐 → 404
- 未认证请求 → 401
- 成功取消收藏 → 204
- 取消未收藏的音乐 → 204（幂等）
- 查询收藏列表 → 200，包含音乐嵌套信息
- 查询空列表 → 200，空数组

### 专辑收藏（同上模式）
- 成功收藏/取消收藏/列表查询
- 收藏不存在的专辑 → 404
- 专辑被软删除后不可收藏 → 404

### 歌单收藏（同上模式）
- 成功收藏/取消收藏/列表查询
- 收藏不存在的歌单 → 404

### 已发布音乐标记
- 成功标记/取消标记/列表查询
- 标记不存在的音乐 → 404

---

## 成功标准

- `pytest tests/test_collection.py -v` 全部通过
- `pytest tests/ -v` 全量回归通过（现有 103 个测试不失败）
- 无新增 warnings 或 errors
