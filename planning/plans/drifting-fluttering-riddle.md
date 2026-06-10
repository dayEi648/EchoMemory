# 计划：专辑管理页面开发

## 上下文

前端管理后台已具备用户管理、音乐管理、字典维护等完整功能，但**缺少专辑管理页面**。后端专辑 API 已提供创建、更新、删除、歌曲增删等基础能力，但存在两个缺口：
1. **无管理员专用列表接口** — 现有公开搜索 `/albums/search` 返回的 `AlbumListOut` 不含作者和歌曲数，不足以支撑管理表格展示。
2. **编辑时不支持替换封面** — `PATCH /albums/admin/{album_id}` 仅接受 JSON，无法上传新的封面图片文件。

## 前端功能构思（不以后端为上限）

管理页面应包含以下功能模块：

### 1. 专辑列表（主页面）
- 表格列：ID、封面图标、标题、作者（昵称列表）、歌曲数、播放量、收藏数、创建时间、操作
- 搜索栏：按标题关键词搜索
- 分页（支持每页条数切换）
- 操作按钮：编辑、删除、管理歌曲

### 2. 新建专辑弹窗
- 双栏布局（与音乐导入/编辑弹窗风格一致）
- 左栏：标题（*必填）、描述、来源
- 右栏：封面图标（*必填，图片上传）、封面大图（*必填，图片上传）、作者选择（搜索用户，多选）

### 3. 编辑专辑弹窗
- 同新建弹窗布局，预填充当前数据
- 封面图标/封面大图支持替换（上传新图替换旧图）
- 作者支持增删

### 4. 歌曲管理弹窗
- 上方显示专辑标题和当前歌曲数
- 歌曲列表：序号、封面、标题、VIP 标识、操作（移除）
- 添加歌曲区域：搜索已上架音乐（通过现有音乐搜索接口），下拉选择后点击添加
- 后端会自动同步专辑标签（根据歌曲标签聚合）

### 5. 删除确认弹窗
- 输入专辑标题确认后执行软删除

## 后端需要补充的接口

### 新增 1：管理员专辑列表接口
- **路径**：`GET /albums/admin/list`
- **位置**：必须在 `/admin/{album_id}` 之前注册（FastAPI 路由顺序要求）
- **参数**：`q`（标题搜索，可选）、`limit`、`offset`
- **响应**：`PaginatedAdminAlbumListOut`
  - `items`: `AdminAlbumListItem[]` — 在 `AlbumListOut` 基础上增加 `authors: AlbumAuthorOut[]` 和 `music_count: int`
  - `total`: `int`
- **服务模式**：参考 `music_service.admin_search_musics`，新增 `album_service.admin_search_albums`，返回 `{"items": ..., "total": ...}`
- **Schema 新增**：`AdminAlbumListItem`、`PaginatedAdminAlbumListOut`

### 新增 2：专辑封面替换接口
- **路径**：`PATCH /albums/admin/{album_id}/covers`
- **参数**：`cover_icon`（UploadFile，可选）、`cover`（UploadFile，可选）
- **行为**：
  1. 校验上传文件为图片类型
  2. 上传新图片到 OSS（folder="album_covers"）
  3. 删除旧 OSS 图片（如有）
  4. 更新数据库中 `cover_icon_url` / `cover_url`
  5. 若后续步骤失败，回滚已上传的 OSS 文件（与创建专辑保持一致的错误处理）
- **响应**：`AlbumOut`
- **服务新增**：`album_service.update_album_covers`

## 实施步骤

### Phase 1：后端扩展（先补缺口，再写前端）
1. **Schema 层** (`schemas/album.py`)：新增 `AdminAlbumListItem`、`PaginatedAdminAlbumListOut`
2. **服务层** (`services/album_service.py`)：
   - 新增 `admin_search_albums(db, q, limit, offset) -> dict[str, object]`
   - 新增 `update_album_covers(db, album, cover_icon_file, cover_file) -> Album`
3. **API 层** (`api/v1/endpoints/album.py`)：
   - 新增 `GET /admin/list`（放在 `GET /admin/{album_id}` 之前）
   - 新增 `PATCH /admin/{album_id}/covers`
4. **测试** (`tests/test_album.py`)：为新增接口补充 pytest 测试

### Phase 2：前端页面开发
5. **API 层** (`shared/api/albumApi.ts`)：
   - 新增 `adminListAlbums(q, limit, offset)`
   - 新增 `adminUpdateAlbumCovers(albumId, cover_icon?, cover?)`
6. **类型层** (`shared/api/types.ts`)：新增 `AdminAlbumListItem`、`PaginatedAdminAlbumList`
7. **新建页面** (`pages/admin/AdminAlbumPage.tsx`)：完整实现列表、弹窗、操作逻辑
8. **路由** (`App.tsx`)：新增 `/admin/albums` 路由
9. **导航** (`pages/admin/AdminSideNav.tsx`)：新增"专辑管理"导航项

## 关键文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `apps/backend/src/echomemory_backend/schemas/album.py` | 修改 | 新增 AdminAlbumListItem、PaginatedAdminAlbumListOut |
| `apps/backend/src/echomemory_backend/services/album_service.py` | 修改 | 新增 admin_search_albums、update_album_covers |
| `apps/backend/src/echomemory_backend/api/v1/endpoints/album.py` | 修改 | 新增两个管理员端点 |
| `apps/backend/tests/test_album.py` | 修改 | 新增测试用例 |
| `apps/frontend/src/shared/api/types.ts` | 修改 | 新增前端类型 |
| `apps/frontend/src/shared/api/albumApi.ts` | 修改 | 新增 API 方法 |
| `apps/frontend/src/pages/admin/AdminAlbumPage.tsx` | **新建** | 专辑管理主页面 |
| `apps/frontend/src/App.tsx` | 修改 | 注册 /admin/albums 路由 |
| `apps/frontend/src/pages/admin/AdminSideNav.tsx` | 修改 | 添加导航入口 |

## 复用资源

- **表单组件**：`pages/admin/_musicFormComponents.tsx` 中的 `ImagePreviewZone`、`AuthorSelect` 可直接复用于封面上传和作者选择
- **通用组件**：`Modal`、`PaginationBar`、`EmptyState`、`FadeIn`、`StaggerContainer`、`SongRow`
- **布局模式**：参考 `AdminMusicPage` 的表格 + 筛选 + 弹窗交互模式
- **动画**：复用现有 `framer-motion` 动画（`whileHover`、`whileTap`、`AnimatePresence`）

## 验证方式

1. 启动后端服务，使用 pytest 运行专辑相关测试，确保新增接口测试通过
2. 启动前端开发服务器，访问 `/admin/albums`
3. 端到端验证：
   - [ ] 列表正常加载，显示封面、标题、作者、歌曲数
   - [ ] 搜索功能正常，分页切换正常
   - [ ] 新建专辑：填写信息、上传封面、选择作者后成功创建
   - [ ] 编辑专辑：修改文本信息、替换封面后成功更新
   - [ ] 歌曲管理：打开弹窗显示歌曲列表，添加新歌曲、移除歌曲均正常
   - [ ] 删除专辑：输入标题确认后专辑消失（软删除）
