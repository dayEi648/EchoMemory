# 计划：歌单模块 + 播放列表智能队列

## 背景

当前前端缺少歌单模块的功能页面（PlaylistsPage 是 mock 数据，无歌单详情页），且播放器的队列管理不完整：从搜索/首页点击单曲时队列为空，从专辑点击单曲时应该把整个专辑作为队列但没有做。这导致播放器的"上一首/下一首"行为不一致。

## 需要改动的文件

### 1. 新增：`apps/frontend/src/shared/api/playlistApi.ts`

创建歌单 API 客户端，遵循与 `albumApi.ts` / `musicApi.ts` 相同的模式（使用 `createBaseApi`）。

暴露方法：
- `listPlaylists(params)` → `GET /playlists/`
- `getPlaylistDetail(id)` → `GET /playlists/{id}`
- `createPlaylist(input)` → `POST /playlists/` (multipart form)
- `updatePlaylist(id, input)` → `PATCH /playlists/{id}`
- `deletePlaylist(id)` → `DELETE /playlists/{id}`
- `addMusicToPlaylist(playlistId, musicId)` → `POST /playlists/{id}/musics/{musicId}`
- `removeMusicFromPlaylist(playlistId, musicId)` → `DELETE /playlists/{id}/musics/{musicId}`

### 2. 修改：`apps/frontend/src/shared/api/types.ts`

新增歌单相关 TypeScript 类型：
- `PlaylistUser` — 歌单中的用户精简信息
- `PlaylistMusic` — 歌单中的歌曲项（含 `music: MusicListItem`, `ordinal`）
- `PlaylistDetail` — 歌单详情（对应 `PlaylistOut`）
- `PlaylistListItem` — 歌单列表项（对应 `PlaylistListOut`）
- `PaginatedPlaylistList` — 分页歌单列表
- `PlaylistUpdateInput` — 更新歌单请求体

### 3. 修改：`apps/frontend/src/shared/stores/playerStore.ts`

这是本次的核心改动：

**新增状态：**
- `queueContext: QueueContext | null` — 描述当前队列的来源

**新增类型：**
```ts
type QueueContext = 
  | { type: 'playlist'; id: number; name: string }
  | { type: 'album'; id: number; name: string }
  | { type: 'history' }
  | null
```

**新增方法：`playInContext(track, contextTracks, contextInfo)`**
- 接受一首歌 + 上下文歌曲列表 + 上下文信息
- 将队列设为上下文歌曲列表，定位到当前歌曲的索引，开始播放
- 设置 `queueContext`

**修改方法：`next()` 和 `prev()`**
- 当下一首/上一首歌曲的 `file_url` 为 null 时，通过 `musicApi.getMusicDetail()` 懒加载获取 file_url
- 获取到后更新队列中该歌曲的 file_url，然后播放
- 如果获取失败，跳过该歌曲继续找下一首

**新增方法：`playStandalone(track)`**
- 用于搜索/首页等单独播放场景
- 内部逻辑：获取播放历史（最近 50 条），构建队列 = [当前歌曲, ...历史歌曲（去重）]
- 调用 `_playQueueInternal()` 设定队列并开始播放

### 4. 新增：`apps/frontend/src/pages/PlaylistDetailPage.tsx`

新页面，路由 `/playlist/:playlistId`。

**页面结构：**
- 返回按钮
- 歌单封面 + 标题 + 描述 + 创建者信息
- "播放全部" 按钮
- 歌曲列表（使用 `SongRow` 组件），按 `ordinal` 排序
- 点击单曲 → 使用 `playInContext` 以整个歌单为队列上下文播放
- 空状态：无歌曲时显示提示

### 5. 修改：`apps/frontend/src/pages/PlaylistsPage.tsx`

将 mock 数据替换为真实 API：

- 调用 `playlistApi.listPlaylists()` 获取当前用户的歌单列表
- 保留分类标签作为装饰（后端暂不支持按分类筛选）
- 每个歌单卡片点击 → 导航到 `/playlist/:id`
- 添加分页（`PaginationBar`）
- 空状态：无歌单时显示引导提示
- 移除 mock 数据数组

### 6. 修改：`apps/frontend/src/App.tsx`

新增路由：
```tsx
<Route path="/playlist/:playlistId" element={<PlaylistDetailPage />} />
```

### 7. 修改：播放上下文相关的现有页面

**AlbumDetailPage.tsx** — 点击单曲时：
- 当前：`playTrack(singleTrack)` → 队列不更新
- 改为：`playInContext(singleTrack, allAlbumTracksWithUrl, { type: 'album', id: album.id, name: album.title })`

**DiscoverPage.tsx** — 新歌/排行榜区域点击单曲时：
- 当前：`playTrack(singleTrack)` → 队列不更新
- 改为：`playStandalone(singleTrack)` → 自动拼接历史歌曲队列

**SearchPage.tsx** — 搜索结果的歌曲点击：
- 当前：`playTrack(singleTrack)` → 队列不更新
- 改为：`playStandalone(singleTrack)`

**HistoryPage.tsx** — 播放历史中的歌曲点击：
- 当前：`playTrack(singleTrack)` → 队列不更新
- 改为：`playStandalone(singleTrack)`

**MusicDetailPage.tsx** — 歌曲详情页和相关推荐点击：
- 当前：`playTrack(singleTrack)`
- 改为：`playStandalone(singleTrack)`

### 8. 修改：`apps/frontend/src/components/layout/PlayerBar.tsx`

队列面板（Queue Panel）增强：
- 顶部显示队列来源：歌单名 / 专辑名 / "播放历史"
- 显示当前队列上下文信息

## 依赖关系

- 所有改动依赖 `playerStore` 的增强 → 先改 playerStore
- `PlaylistDetailPage` 依赖 `playlistApi` → 先创建 API 层
- 页面改动依赖 `playInContext` / `playStandalone` 方法 → 最后改页面

## 实施顺序

1. 类型定义（`types.ts`）
2. API 层（`playlistApi.ts`）
3. playerStore 增强（`playerStore.ts`）
4. PlayerBar 队列面板增强（`PlayerBar.tsx`）
5. PlaylistDetailPage（新建）
6. PlaylistsPage（替换 mock）
7. App.tsx（添加路由）
8. 更新所有页面的播放逻辑（AlbumDetailPage, DiscoverPage, SearchPage, HistoryPage, MusicDetailPage）

## 验证

1. `npm run build` / `npm run dev` — 前端编译无错误
2. 播放列表广场页面：加载真实歌单数据，分页工作正常，空状态显示正确
3. 歌单详情页：显示歌单歌曲列表，点击歌曲在歌单上下文播放，上下首切换在歌单内
4. 专辑详情页：点击单曲在专辑上下文播放
5. 首页/搜索/历史：点击单曲自动拼接历史队列播放
6. PlayerBar 队列面板：显示当前队列来源标签，队列列表内容正确
