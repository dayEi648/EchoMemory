# 私人漫游（Private Roam）后端开发计划

## Context

echomemory 首页"发现页"有三张推荐入口卡片：每日推荐（已完成）、私人雷达（已完成）、私人漫游（纯占位，`path: null`）。用户设计了私人漫游的产品逻辑，要求后端先行，遵循测试驱动开发。

### 产品定义（用户确认）

1. **冷启动**：第一首歌纯随机，不使用任何已有用户偏好数据——这是和每日推荐/私人雷达的核心差异化
2. **反馈驱动**：用户操作（收藏/不喜欢）动态影响偏好池，下一首基于池加权随机推荐
3. **池生命周期**：preference pool 和 dislike pool 每天凌晨 4 点（UTC+8）自动清空
4. **导航逻辑**：上一首/下一首是纯导航；池变化只在新生成歌曲时生效
5. **无操作**：既不收藏也不不喜欢时，不改变任何池

### 设计决策（我建议，用户认可）

| 决策 | 内容 |
|------|------|
| 不喜欢交互 | 两级反馈：点"下一首"=隐式负反馈（歌曲级，权重低），点"👎"=可弹出面板选具体不喜欢维度 |
| 颗粒度 | song_id 级（只屏蔽这首歌）、artist_id 级、标签级（仅用户明确选择时） |
| 收藏目标 | 默认收藏到"我喜欢的音乐"系统歌单 |
| 存储 | Redis，key 当天过期（SGT 4am），无需持久化 |
| 下一首算法 | 基于 preference/dislike pool 加权评分 + 随机因子，从 top K 候选中加权随机选择 |
| 导航 | 上一首/下一首纯导航；池变化不影响已生成歌曲 |

---

## 实现方案

### 1. Redis Key 设计

```
roam:pref:{user_id}    Hash  { "emotion:{id}":"+2", "interest:{id}":"+1", "style:{id}":"+3", "language:{id}":"+1" }
roam:dislike:{user_id} Hash  { "song:{id}":"1", "artist:{id}":"1", "emotion:{id}":"-1", "style:{id}":"-2" }
roam:playlist:{user_id} List  [ "42", "17", "89" ]  -- 歌曲 ID 字符串
roam:position:{user_id} String "1"  -- 当前播放位置的索引
```

- 所有 key 在首次创建时设置 TTL = 距离当天 UTC+8 凌晨 4:00 的秒数
- 复用项目已有的 `redis_client.redis_client`（`redis.asyncio.from_url` 实例，`decode_responses=True`）

### 2. 新文件清单

| 文件 | 用途 |
|------|------|
| `services/roam_service.py` | 核心业务逻辑 |
| `schemas/roam.py` | Pydantic 请求/响应模型 |
| `api/v1/endpoints/roam.py` | REST API 端点 |
| `tests/test_roam.py` | 测试（TDD 先行） |

### 3. 需修改的文件

| 文件 | 改动 |
|------|------|
| `api/v1/router.py` | 注册 `roam.router` |

---

### 4. 服务层 `services/roam_service.py`

#### 4.1 常量

```python
_ROAM_PREFIX = "roam"
_DEFAULT_CANDIDATE_POOL_SIZE = 30  # 加权评分时取 top 30 候选
```

#### 4.2 核心函数

| 函数 | 签名 | 职责 |
|------|------|------|
| `_roam_key()` | `(user_id, suffix) -> str` | 生成 `roam:{suffix}:{user_id}` |
| `_seconds_until_4am_cst()` | `() -> int` | 距 UTC+8 4am 秒数 |
| `_ensure_ttl()` | `(key) -> None` | 新 key 设置 TTL |
| `_get_music_tag_ids()` | `(db, music_id) -> dict` | 获取音乐的情绪/兴趣/风格/语言/作者 ID |
| `_score_candidates()` | `(db, candidates, pref_pool, dislike_pool) -> list[tuple[Music, float]]` | 加权评分 |
| `start_roam()` | `(db, user_id) -> dict` | 初始化 session，生成第一首歌 |
| `get_roam_state()` | `(user_id) -> dict` | 获取当前 session 状态 |
| `next_song()` | `(db, user_id) -> dict` | 下一首（导航或生成） |
| `prev_song()` | `(user_id) -> dict` | 上一首（纯导航） |
| `favorite_song()` | `(db, user_id, song_id) -> dict` | 收藏 + 更新 pref pool |
| `dislike_song()` | `(user_id, song_id, reasons?) -> dict` | 不喜欢 + 更新 dislike pool |
| `_generate_next_song()` | `(db, user_id) -> Music` | 基于池加权随机推荐 |

#### 4.3 加权评分算法 `_score_candidates`

```
对每个候选歌曲：
  score = 0.0
  
  # 偏好匹配（正分）
  for tag in song.tags:
    if tag in pref_pool:
      score += pref_pool[tag]  # 权重值（正数）
  
  # 不喜欢匹配（负分）
  if song.id in dislike_pool.songs:
    score -= 10.0  # 歌曲级，大负分
  if song.artist_id in dislike_pool.artists:
    score -= 5.0   # 艺术家级，中等负分
  for tag in song.tags:
    if tag in dislike_pool.tags:
      score += dislike_pool[tag]  # 权重值（负数）
  
  # 随机因子（探索性）
  score += random.uniform(0, 3.0)

取 score 最高的 30 首 → 按 softmax(score * 0.5) 概率随机选 1 首
```

### 5. Schema 层 `schemas/roam.py`

```python
class RoamStateOut(BaseModel):
    playlist: list[int]         # 已生成的音乐 ID 列表（有序）
    position: int               # 当前位置索引
    current_song: MusicOut      # 当前歌曲详情
    pref_pool_summary: dict     # 偏好池摘要
    dislike_pool_summary: dict  # 不喜欢池摘要

class RoamDislikeReasons(BaseModel):
    emotion_tag_ids: list[int] | None = None
    interest_tag_ids: list[int] | None = None
    style_id: int | None = None
    language_id: int | None = None`
```

### 6. API 层 `api/v1/endpoints/roam.py`

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/roam/start` | ✅ | 开始新漫游 session |
| GET | `/roam/state` | ✅ | 获取当前状态 |
| POST | `/roam/next` | ✅ | 下一首 |
| POST | `/roam/prev` | ✅ | 上一首 |
| POST | `/roam/{song_id}/favorite` | ✅ | 收藏当前歌曲 |
| POST | `/roam/{song_id}/dislike` | ✅ | 不喜欢当前歌曲 |

路由注册到 v1：`/api/v1/roam/...`

### 7. 测试 `tests/test_roam.py`（TDD）

测试文件命名遵循项目约定，参考 `test_recommendations.py` 的模式（pytest + TestClient + 真实 PostgreSQL + FakeRedis）。

**测试用例**：

| # | 测试 | 说明 |
|---|------|------|
| 1 | `test_start_roam_returns_one_song` | 开始漫游返回 1 首随机歌曲 |
| 2 | `test_roam_state_reflects_playlist_and_position` | 状态接口返回正确的列表和位置 |
| 3 | `test_next_generates_new_song_when_at_end` | 在列表末尾点下一首，生成新歌 |
| 4 | `test_next_navigates_without_generating` | 回到之前的歌再下一首，不生成新歌 |
| 5 | `test_prev_navigates_back` | 点上一首回到前一首 |
| 6 | `test_prev_at_start_does_not_go_below_zero` | 在第一首点上一首不越界 |
| 7 | `test_favorite_updates_pref_pool` | 收藏后偏好池有对应标签 |
| 8 | `test_dislike_without_reasons_blocks_song_only` | 无原因的不喜欢只屏蔽歌曲 ID |
| 9 | `test_dislike_with_reasons_blocks_tags` | 带原因的不喜欢屏蔽对应标签 |
| 10 | `test_next_song_respects_pref_pool` | 偏好池影响了后续推荐（标签匹配率提升） |
| 11 | `test_next_song_respects_dislike_pool` | 不喜欢池排除了对应歌曲 |
| 12 | `test_roam_pool_expires_at_4am` | 验证 TTL 计算正确 |
| 13 | `test_unauthenticated_access_rejected` | 无认证请求被拒绝 |

---

## 验证方式

1. **单元测试**：`pytest tests/test_roam.py -v` 全部通过
2. **集成测试**：`pytest tests/test_roam.py tests/test_recommendations.py -v` 确保不与现有推荐模块冲突
3. **手动验证**（后端完成后）：
   - 用 Swagger UI（`/docs`）测试完整漫游流程
   - 验证 Redis key 存在且 TTL 正确
   - 验证凌晨 4 点后 key 自动过期
