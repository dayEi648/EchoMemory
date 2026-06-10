# 前端音乐模块开发计划

## Context

当前前端用户模块已完全闭环（认证、资料、搜索、后台用户管理），但音乐核心链路全部停留在占位/mock 阶段。后端已具备完整的音乐、专辑、播放历史、字典数据等 API。本计划旨在打通前端音乐播放、发现浏览、听歌计数、管理后台音乐管理等核心链路，让应用从"用户系统"进化为"音乐平台"。

---

## 设计决策

### 1. 音频播放方案
- **采用 HTML5 Audio API**（`new Audio()`），无需任何额外 npm 依赖
- Tauri v2 WebView2 完全支持音频流播放；CSP 为 null，无限制
- 音频源为后端返回的 `file_url`（OSS 公共读 URL）
- 播放器状态由独立 Zustand store 管理，与 `authStore` 解耦

### 2. 听歌计数策略
- 播放一首歌时，通过 `HTMLAudioElement` 的 `onplay` 事件触发计时
- 当真实播放时长累计 ≥ 30 秒 或 播放完成 ≥ 50% 时，调用 `POST /play-history/` 记录一次播放
- 使用防抖：同一首歌同一次播放会话只记录一次，切换歌曲或播放结束时重置

### 3. 数据流架构
- **API 层**：新建 `musicApi.ts`、`albumApi.ts`、`playHistoryApi.ts`、`dictionaryApi.ts`，完全复用 `userApi.ts` 的工厂模式（`ApiOptions` + `request<T>` + 自动 refresh）
- **Store 层**：新建 `playerStore.ts`（Zustand），管理当前歌曲、播放队列、播放状态、进度、音量、循环/随机模式
- **页面层**：通过 store 消费播放器状态，通过 API 获取服务端数据

### 4. 后台音乐管理
- `/admin/music`：音乐列表页，支持搜索、筛选（上架状态、风格、语言）、分页
- `/admin/music/import`：音乐导入表单页（复用已有 Modal 或独立页面，这里用独立页面避免 Modal 过大）
- 上架/下架操作直接在列表页完成，编辑操作跳转到详情编辑

---

## 开发步骤

### Step 1: 类型定义与 API 客户端（4 个文件）

1. **`src/shared/api/types.ts`** — 追加音乐/专辑/播放历史/字典相关 TypeScript 类型：
   - `Music`, `MusicListItem`, `MusicUpdateInput`, `Author`, `Instrument`, `Tag`
   - `Album`, `AlbumListItem`, `AlbumMusicItem`, `AlbumCreateInput`, `AlbumUpdateInput`
   - `PlayHistoryItem`, `PlayHistoryCreateInput`
   - `DictionaryItem`, `DictionaryType`

2. **`src/shared/api/musicApi.ts`** — 音乐 API 客户端：
   - `searchMusic(q?, styleId?, languageId?, limit?, offset?)`
   - `listMusic(styleId?, languageId?, isVip?, limit?, offset?)`
   - `getMusicDetail(musicId)`
   - `adminImportMusic(formData)`
   - `adminUpdateMusic(musicId, data)`
   - `adminPublishMusic(musicId)` / `adminUnpublishMusic(musicId)`

3. **`src/shared/api/albumApi.ts`** — 专辑 API 客户端：
   - `searchAlbums(q?, limit?, offset?)`
   - `listAlbums(emotionTagId?, interestTagId?, limit?, offset?)`
   - `getAlbumDetail(albumId)`
   - `adminCreateAlbum(formData)` / `adminUpdateAlbum(albumId, data)` / `adminDeleteAlbum(albumId)`
   - `adminAddMusicToAlbum(albumId, musicId)` / `adminRemoveMusicFromAlbum(albumId, musicId)`

4. **`src/shared/api/playHistoryApi.ts`** — 播放历史 API 客户端：
   - `recordPlay(musicId)`
   - `listPlayHistory(limit?, offset?)`
   - `deletePlayHistory(historyId)` / `clearPlayHistory()`

5. **`src/shared/api/dictionaryApi.ts`** — 字典数据 API 客户端：
   - `listDictionary(type)` — type: 'styles' | 'languages' | 'instruments' | 'emotion_tags' | 'interest_tags'

### Step 2: 播放器状态管理（1 个文件）

**`src/shared/stores/playerStore.ts`** — Zustand store：
- State: `currentTrack: MusicListItem | null`, `queue: MusicListItem[]`, `queueIndex: number`, `isPlaying: boolean`, `progress: number`, `duration: number`, `volume: number`, `isShuffle: boolean`, `isRepeat: boolean`, `audioElement: HTMLAudioElement | null`
- Actions: `playTrack(track)`, `playQueue(queue, startIndex)`, `togglePlay()`, `next()`, `prev()`, `seek(percent)`, `setVolume(vol)`, `toggleShuffle()`, `toggleRepeat()`
- 内部监听 `audio` 事件（timeupdate, ended, error）以同步状态
- 内部集成听歌计数逻辑：播放 30s 后自动调用 `playHistoryApi.recordPlay()`

### Step 3: 改造 PlayerBar（1 个文件）

**`src/components/layout/PlayerBar.tsx`**：
- 接入 `playerStore`，替换所有本地 state
- 显示真实歌曲封面（`cover_icon_url`）、歌名、作者
- 播放/暂停按钮真实控制 audio
- 进度条可拖拽/点击跳转（通过 `seek()`）
- 上一首/下一首真实切换队列
- 音量按钮控制音量（点击展开滑块）
- 播放队列按钮（点击展开当前队列面板）
- 无歌曲时保持现有占位状态

### Step 4: 改造发现页（1 个文件）

**`src/pages/DiscoverPage.tsx`**：
- 组件加载时调用 `musicApi.listMusic()` 获取新歌上架列表
- 调用 `albumApi.listAlbums()` 获取推荐专辑列表
- 调用 `playHistoryApi.listPlayHistory(limit=5)` 获取最近播放
- 替换所有 mock 数据为真实数据
- SongRow 增加 `onPlay` prop，点击播放对应歌曲
- CoverCard 增加 `coverUrl` prop，支持显示真实封面（OSS URL）
- Hero CTA "播放今日推荐" 点击后播放新歌列表第一首

### Step 5: 新建音乐详情页（1 个文件）

**`src/pages/MusicDetailPage.tsx`**：
- 路由：`/music/:musicId`
- 展示歌曲封面、歌名、作者、风格、语言、播放量、发布时间
- "播放" 主按钮（接入 playerStore）
- 下方相关推荐（同风格/同语言的歌曲列表）

### Step 6: 新建专辑详情页（1 个文件）

**`src/pages/AlbumDetailPage.tsx`**：
- 路由：`/album/:albumId`
- 展示专辑封面、标题、描述、作者、歌曲列表
- 歌曲列表支持点击播放、点击跳转到音乐详情
- "播放全部" 按钮（将整个专辑加入队列并播放）

### Step 7: 改造搜索页（1 个文件）

**`src/pages/SearchPage.tsx`**：
- "歌曲" Tab：接入 `musicApi.searchMusic(q)` 真实搜索
- "专辑" Tab：接入 `albumApi.searchAlbums(q)` 真实搜索
- 搜索结果以列表/卡片形式展示，支持点击播放或跳转详情
- "歌单" Tab 保持占位（即将上线）

### Step 8: 新建播放历史页（1 个文件）

**`src/pages/HistoryPage.tsx`**：
- 替换空状态为真实数据
- 接入 `playHistoryApi.listPlayHistory()`
- 展示历史记录列表，支持点击播放、删除单条、清空全部

### Step 9: 新建后台音乐管理页（1 个文件）

**`src/pages/admin/AdminMusicPage.tsx`**：
- 路由：`/admin/music`
- 表格展示所有音乐（含未上架的），列：ID、封面、歌名、作者、风格、语言、播放量、上架状态、操作
- 搜索栏（按歌名模糊搜索）
- 筛选：上架状态、风格、语言（下拉选择，数据来源 dictionaryApi）
- 分页
- 操作按钮：上架/下架切换、编辑（弹出 Modal 修改元数据）、删除（确认弹窗）
- "导入音乐" 按钮跳转到 `/admin/music/import`

### Step 10: 新建后台音乐导入页（1 个文件）

**`src/pages/admin/AdminMusicImportPage.tsx`**：
- 路由：`/admin/music/import`
- 大表单：歌名、音频文件、封面 icon、封面 home、封面 play、歌词文件、是否 VIP、来源、发行日期
- 风格/语言/乐器/情感标签/兴趣标签：多选下拉（数据来源 dictionaryApi）
- 作者：多选用户搜索（可复用现有用户搜索 API）
- 提交为 multipart/form-data
- 成功提示并跳回列表页

### Step 11: 路由更新（1 个文件）

**`src/App.tsx`**：
- 新增 `/music/:musicId` → `MusicDetailPage`
- 新增 `/album/:albumId` → `AlbumDetailPage`
- 后台路由新增 `/admin/music` → `AdminMusicPage`
- 后台路由新增 `/admin/music/import` → `AdminMusicImportPage`

### Step 12: UI 组件增强（2 个文件）

**`src/components/ui/CoverCard.tsx`**：
- 新增可选 `coverUrl?: string` prop，传入时显示真实封面图而非渐变
- 保持向后兼容：无 coverUrl 时继续显示渐变

**`src/components/ui/SongRow.tsx`**：
- 新增 `musicId: number`、`coverUrl?: string`、`onPlay?: () => void` props
- 点击行可跳转 `/music/:musicId`
- hover 时显示播放按钮，点击播放按钮触发 `onPlay`
- 保持向后兼容：无新 props 时保持原有行为

---

## 验证标准

- [ ] 打开发现页，能看到真实的音乐列表和专辑列表（非 mock）
- [ ] 点击歌曲行的播放按钮，PlayerBar 显示真实歌曲信息并开始播放
- [ ] PlayerBar 的进度条随播放推进，暂停/播放按钮真实生效
- [ ] 播放超过 30 秒后，后端 `play_history` 表产生记录
- [ ] 搜索页切换到"歌曲"/"专辑" Tab，输入关键词能返回真实结果
- [ ] 管理员进入后台 `/admin/music`，能看到音乐列表，可执行上架/下架操作
- [ ] 管理员可通过导入页上传音乐文件并成功导入
- [ ] 所有现有测试（`npm test`）继续通过

---

## 关键复用点

| 功能 | 复用来源 |
|------|----------|
| API 工厂模式（自动 refresh） | `userApi.ts` |
| FormData 构建工具 | `userApi.ts` 中的 `appendDefined` |
| 分页表格 + 筛选 + Modal | `UserManagementPage.tsx` |
| 动画组件 | `FadeIn.tsx`, `StaggerContainer.tsx` |
| 空状态 | `EmptyState.tsx` |
| 自定义 CSS 变量 | `index.css` 中已有的 design tokens |
| 路由守卫 | 现有 `AdminRouteGuard` |
