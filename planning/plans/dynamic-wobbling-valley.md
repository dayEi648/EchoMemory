# 发现音乐页（DiscoverPage）重新设计

## Context

当前 DiscoverPage 仅有简单的 hero banner + 推荐专辑 + 新歌上架三个区块，功能单一、信息密度低，与主流音乐平台（网易云音乐、QQ音乐、Spotify）的首页差距较大。需要重新设计为内容丰富的发现页面，包含轮播、每日推荐、私人入口、推荐歌单、各类榜单等模块。

由于推荐/榜单等后端接口尚未开发，所有数据区块均以**占位数据**呈现，待接口就绪后接入真实数据。

---

## 1. 页面布局设计

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ██████████████████████████████████████████████████████  │  ← Hero Carousel
│  ████████████  Carousel Banner (3~5 张)  ██████████████  │     auto-rotate 5s
│  ██████████████████████████████████████████████████████  │     dot indicators
│  ● ○ ○ ○                                                │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  每日推荐             私人雷达          私人漫游          │  ← Daily + Personal
│  ┌────────┐          ┌────────┐       ┌────────┐        │     3 列网格
│  │ cover  │          │ cover  │       │ cover  │        │
│  │ title  │          │ title  │       │ title  │        │
│  │  subtitle         │  subtitle      │  subtitle       │
│  └────────┘          └────────┘       └────────┘        │
├──────────────────────────────────────────────────────────┤
│  推荐歌单                                   查看更多 →    │  ← Recommended
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐            │     CoverCard grid
│  │    │ │    │ │    │ │    │ │    │ │    │            │     (playlist-rail)
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘            │
├──────────────────────────────────────────────────────────┤
│  热门榜单                                                │  ← Charts
│  ┌──────────┬──────────┬──────────┐                     │     3 列
│  │ 🔥 热歌榜 │ 🆕 新歌榜 │ 👑 VIP榜 │                     │     每列显示 Top 5
│  │ 1. xxx   │ 1. xxx   │ 1. xxx   │                     │     SongRow 精简版
│  │ 2. xxx   │ 2. xxx   │ 2. xxx   │                     │
│  │ 3. xxx   │ 3. xxx   │ 3. xxx   │                     │
│  └──────────┴──────────┴──────────┘                     │
├──────────────────────────────────────────────────────────┤
│  最新上架                                    查看全部 →  │  ← New Releases
│  [SongRow] [SongRow] [SongRow] [SongRow] ...            │     full SongRow
│  [SongRow] [SongRow] [SongRow] [SongRow] ...            │
└──────────────────────────────────────────────────────────┘
```

---

## 2. 新建组件

### 2.1 HeroCarousel（新建）
**文件**: `apps/frontend/src/components/ui/HeroCarousel.tsx`

- 3~5 张占位轮播图，用品牌渐变色 + 大标题 + 副标题模拟
- 自动轮播（5 秒间隔），带手动 dot indicator 切换
- framer-motion AnimatePresence 实现淡入淡出过渡
- 箭头按钮（左右切换）
- Props: `slides: { title, subtitle, gradient, action? }[]`

### 2.2 ChartColumn（新建）
**文件**: `apps/frontend/src/components/ui/ChartColumn.tsx`

- 榜单列组件，标题 + icon + Top N 歌曲列表
- 精简歌曲条目：序号 + 歌名 + 艺人（无封面）
- "查看全部" 链接
- Props: `title, icon, accent, songs: MusicListItem[], onViewAll?`

---

## 3. 修改文件

### 3.1 DiscoverPage.tsx（重写）
- 移除旧的 hero banner / sidebar / level progress / recent plays
- 添加新的五大区块：HeroCarousel、Daily+Personal、Recommended Playlists、Charts、New Releases
- 所有数据区块使用占位数据（硬编码 slides、空列表 + EmptyState 变体）
- 保留 `loading` 状态和 framer-motion 动画
- 移除不再需要的旧状态：`recentPlays`、`newSongs`、`albums`

### 3.2 index.css（新增样式）
- `.hero-carousel` — 轮播容器
- `.hero-carousel-slide` — 单张轮播图
- `.hero-carousel-dots` — dot indicator
- `.hero-carousel-arrow` — 左右箭头
- `.discover-daily-grid` — 每日推荐/私人入口 3 列网格
- `.discover-daily-card` — 每日推荐卡片
- `.chart-column` — 榜单列
- `.chart-song-item` — 榜单歌曲条目（精简版）

---

## 4. 占位数据方案

| 区块 | 占位方式 |
|---|---|---|
| HeroCarousel | 3 张硬编码 slide（不同品牌渐变色 + 中文标题副标题） |
| 每日推荐 | 1 张硬编码卡片（灰色封面占位 + "每日歌曲推荐"） |
| 私人雷达/漫游 | 各 1 张硬编码卡片（封面占位 + 标题 + 副标题说明） |
| 推荐歌单 | 6 个 CoverCard（调用 `albumApi.listAlbums` 或硬编码占位） |
| 热门榜单 | 调用 `musicApi.listMusic` 获取真实歌曲数据（按 hot/play_count 排序） |
| 最新上架 | 调用 `musicApi.listMusic` 获取真实歌曲数据（按 created_at 排序） |

榜单和最新上架可以**使用已有的真实 API**（`musicApi.listMusic`），只是没有专门的"推荐"逻辑，按播放量/时间排序展示即可。

---

## 5. 移除的旧内容

- 旧 hero-banner（含"今日推荐"tag、"欢迎回来，xxx"、"播放今日推荐"按钮、背景动画 orbs）
- 旧 hero-sidebar（最近播放列表 + 等级进度卡片）
- "为你推荐的专辑"区块（合并到推荐歌单）
- "热门新歌"排行区块（改为独立的榜单区块）

---

## 6. 实施步骤

1. 创建 `HeroCarousel.tsx`
2. 创建 `ChartColumn.tsx`
3. 重写 `DiscoverPage.tsx`
4. 在 `index.css` 中添加新样式
5. 验证编译和构建

---

## 7. 验证

- TypeScript 编译零错误
- Vite 构建成功
- 页面视觉效果：轮播自动切换、dot 指示器正确、各区块布局整齐
- 响应式：移动端轮播缩小、网格从 3 列变为 1 列
