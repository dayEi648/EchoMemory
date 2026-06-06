# 开发计划：字典管理模块 + 音乐模块基本功能

## 目标

为 echomemory 后端实现字典管理与音乐模块的基础 API，支撑后续专辑、歌单、收藏等功能的开发。

**关键约束**：
- 音乐数据仅由管理员在后台导入，普通用户不可创建音乐。
- 音乐导入时，音频文件、封面图片、歌词文件均通过上传方式提供，**任何 URL 字段禁止直接填写字符串**。
- 字典数据由管理员维护，普通用户只读。

---

## Phase 1：字典管理模块

### 1.1 功能清单

| 接口 | 权限 | 说明 |
|------|------|------|
| `POST /api/v1/dictionary/{type}` | Admin | 创建字典项 |
| `GET /api/v1/dictionary/{type}` | Public | 列出字典项（分页） |
| `GET /api/v1/dictionary/{type}/{id}` | Public | 获取单个字典项 |
| `PATCH /api/v1/dictionary/{type}/{id}` | Admin | 修改字典项名称 |
| `DELETE /api/v1/dictionary/{type}/{id}` | Admin | 删除字典项（仅当未被引用时） |

**支持的 type**：`styles`, `languages`, `cities`, `instruments`, `emotion_tags`, `interest_tags`

### 1.2 新增文件

- `schemas/dictionary.py` — 字典的 Pydantic Schema
- `services/dictionary_service.py` — 字典的业务逻辑
- `api/v1/endpoints/dictionary.py` — 字典的 API 端点

### 1.3 修改文件

- `api/v1/router.py` — 注册字典路由

### 1.4 技术要点

- `styles` / `languages` / `cities` 主键为 `SmallInteger`；`instruments` / `emotion_tags` / `interest_tags` 主键为 `BigInteger`。
- 删除字典项前需检查是否被引用（如 `style_id` 是否存在于 `musics` 表中），若被引用则拒绝删除并返回 409。
- 公开接口不需要认证；管理员接口使用现有的 `AdminUser` 依赖。

---

## Phase 2：音乐模块 — 基础设施扩展

### 2.1 OSS 上传工具扩展

现有 `oss_client.py` 仅支持图片上传。需新增通用文件上传函数：

- `upload_audio_to_oss(file, music_id) -> str` — 上传音频文件（mp3/flac/wav），校验 MIME 类型
- `upload_lyrics_to_oss(file, music_id) -> str` — 上传歌词文件（txt/lrc），校验 MIME 类型

音频/歌词文件**不压缩**，直接上传 OSS。支持的最大音频文件大小暂定为 50MB。

**新增/修改文件**：
- `core/oss_client.py` — 增加 `upload_file_to_oss` 通用函数 + `upload_audio_to_oss` + `upload_lyrics_to_oss`

### 2.2 音乐 Schema 设计

- `schemas/music.py` — 音乐相关的 Pydantic Schema
  - `MusicCreate`：管理员导入时使用的表单 Schema（不含 URL，含文件上传字段）
  - `MusicOut`：音乐详情输出（含关联的作者、乐器、标签）
  - `MusicListOut`：音乐列表项输出（精简字段）
  - `MusicUpdate`：管理员修改音乐信息的 Schema

### 2.3 音乐 Service 设计

- `services/music_service.py` — 音乐业务逻辑
  - `create_music(...)`：创建音乐记录 + 关联作者/乐器/标签 + 上传文件到 OSS
  - `get_music_by_id(...)`：获取音乐详情（加载关联关系）
  - `list_musics(...)`：分页列表 + 可选筛选（style_id, language_id, is_vip, is_published）
  - `search_musics(...)`：按标题模糊搜索
  - `update_music(...)`：修改音乐信息（不处理文件替换，仅文本字段）
  - `delete_music(...)`：软删除（设置 `is_deleted` 为 True；Music 模型当前无 `is_deleted`，需确认是否需要添加）

> **注意**：现有 `Music` ORM 模型中没有 `is_deleted` 字段。音乐导入后由管理员控制上架（`is_published`），删除操作暂由管理员通过下架实现。后续若需要硬删除或软删除，可再扩展。

---

## Phase 3：音乐模块 — API 端点

### 3.1 管理员接口

| 接口 | 说明 |
|------|------|
| `POST /api/v1/music/admin/import` | 导入新音乐。接收 multipart/form-data：音频文件、歌词文件（可选）、封面图标、首页封面、播放页封面（可选）、以及 JSON/表单字段（title, style_id, language_id, author_ids[], instrument_ids[], emotion_tag_ids[], interest_tag_ids[], release_date, source, is_vip） |
| `PATCH /api/v1/music/admin/{music_id}` | 修改音乐信息（仅文本字段，不含文件） |
| `POST /api/v1/music/admin/{music_id}/publish` | 上架音乐（设置 is_published = True） |
| `POST /api/v1/music/admin/{music_id}/unpublish` | 下架音乐（设置 is_published = False） |

### 3.2 公开接口

| 接口 | 说明 |
|------|------|
| `GET /api/v1/music/{music_id}` | 获取音乐详情（需 is_published=True） |
| `GET /api/v1/music/` | 音乐列表（分页，支持 style_id / language_id / is_vip 筛选） |
| `GET /api/v1/music/search` | 按标题模糊搜索（分页） |

### 3.3 新增文件

- `api/v1/endpoints/music.py` — 音乐 API 端点

### 3.4 修改文件

- `api/v1/router.py` — 注册音乐路由

---

## Phase 4：测试与验证

### 4.1 测试范围

- 字典 CRUD 接口（管理员权限校验、删除被引用项的冲突）
- 音乐导入接口（文件类型校验、必填字段校验、OSS 上传成功后的记录创建）
- 音乐公开查询接口（未上架音乐不可见、分页正确）

### 4.2 测试文件

- `tests/test_dictionary.py`
- `tests/test_music.py`

### 4.3 运行验证

```bash
cd apps/backend
pytest tests/test_dictionary.py tests/test_music.py -v
```

---

## 开发顺序

```
Step 1: 字典 Schema
Step 2: 字典 Service
Step 3: 字典 API + 注册路由
Step 4: 扩展 OSS 上传工具（音频/歌词）
Step 5: 音乐 Schema
Step 6: 音乐 Service
Step 7: 音乐 API（管理员导入 + 公开查询）+ 注册路由
Step 8: 编写测试 + 运行验证
```

每个步骤完成后，代码须保持可运行状态（FastAPI 能正常启动）。
