# 计划：个人空间模块（说说）

## 背景

后端 SpacePost 模块已完整（CRUD + 点赞 + 图片上传），管理员硬删除接口也已就绪。前端目前零实现。需要开发完整的个人空间页面，支持发布、查看、点赞、删除说说。

## 后端 API 摘要

| 端点 | 方法 | 说明 |
|------|------|------|
| `/space-posts/` | POST | 创建说说（multipart: content + files[] + is_private） |
| `/space-posts/` | GET | 分页列表（?user_id= 可查看他人，不传看自己） |
| `/space-posts/{id}` | GET | 查看详情 |
| `/space-posts/{id}` | DELETE | 软删除自己的说说 |
| `/space-posts/{id}/like` | POST | 点赞（幂等） |
| `/space-posts/{id}/like` | DELETE | 取消点赞 |

**Schema 限制：**
- `SpacePostOut` / `SpacePostListOut` 只含 `user_id`，不含用户昵称/头像 — 需前端另行获取
- 无 `like_count` 字段 — 前端本地维护点赞状态
- 无 `is_liked` 字段 — 前端本地追踪

## 实施计划

### 1. 添加类型定义 — `shared/api/types.ts`

新增：
```ts
type SpacePostImage = { image_url: string; ordinal: number }
type SpacePost = { id, user_id, content, is_private, comment_count, images[], created_at, updated_at }
type SpacePostListItem = { id, user_id, content, is_private, comment_count, images[], created_at }
type PaginatedSpacePostList = { items: SpacePostListItem[]; total: number }
```

### 2. 创建 API 层 — `shared/api/spacePostApi.ts`

遵循 `playlistApi.ts` 模式，暴露：
- `listPosts(params)` → GET `/space-posts/`
- `getPost(id)` → GET `/space-posts/{id}`
- `createPost(input)` → POST `/space-posts/` (multipart)
- `deletePost(id)` → DELETE `/space-posts/{id}`
- `likePost(id)` → POST `/space-posts/{id}/like`
- `unlikePost(id)` → DELETE `/space-posts/{id}/like`

### 3. 创建 SpacePostCard 组件 — `components/ui/SpacePostCard.tsx`

可复用的说说卡片组件：

**Props：**
- `post: SpacePostListItem`
- `author: { nickname, avatar_url, username }` — 作者信息（由页面层传入）
- `currentUserId: number`
- `onDelete(postId)` — 删除回调
- `onLike(postId)` — 点赞回调
- `onUnlike(postId)` — 取消点赞回调

**显示：**
- 顶部：头像 + 昵称 + 时间
- 正文：content 文本
- 图片网格：最多 9 张，自适应布局（1 张大图，2-4 张 2 列，5+ 张 3 列）
- 底部操作栏：点赞按钮（带计数提示）+ 评论数 + 删除按钮（仅自己的）

**点赞状态**：组件内部维护 `liked` 状态，初始 false，点击切换。

### 4. 创建 CreatePostForm 组件 — `components/ui/CreatePostForm.tsx`

发布说说表单：

**Props：**
- `onCreated(post)` — 创建成功回调

**功能：**
- 文本输入区（textarea，最多 2000 字）
- 图片上传按钮（多选，最多 9 张）
- 图片预览区（可删除已选图片）
- 隐私开关
- 发布按钮（带 loading 状态）

### 5. 创建 SpacePage — `pages/SpacePage.tsx`

路由设计：
- `/space` → 当前登录用户的个人空间（显示创建表单 + 自己的所有说说，含私密）
- `/space/:userId` → 查看他人空间（只读，仅公开说说）

**页面结构：**
- 若是自己的空间：顶部显示 `CreatePostForm`
- 说说列表（按时间倒序，分页）
- 空状态：无说说时显示引导提示
- 加载状态：骨架屏或 spinner

**作者信息处理：**
- 自己的空间：直接使用 `useAuthStore().user`
- 他人空间：调用 `api.getPublicUser(userId)` 获取作者信息

### 6. 更新导航 — `components/layout/SideNav.tsx`

在现有导航项末尾新增"个人空间"入口：
```ts
{ to: "/space", icon: MessageCircle, label: "个人空间" }
```

放在"社区"分组下（与 AI 回声分开）。

### 7. 注册路由 — `App.tsx`

```tsx
<Route path="/space" element={<SpacePage />} />
<Route path="/space/:userId" element={<SpacePage />} />
```

### 8. 测试更新 — `App.test.tsx`

适配新增的 `/space-posts/` API mock。

## 实施顺序

1. `types.ts` — 新增类型
2. `spacePostApi.ts` — API 层
3. `SpacePostCard.tsx` — 说说卡片组件
4. `CreatePostForm.tsx` — 发布表单组件
5. `SpacePage.tsx` — 主页面
6. `SideNav.tsx` — 导航入口
7. `App.tsx` — 路由注册
8. `App.test.tsx` — 测试适配

## 验证

1. TypeScript 编译通过，Vite 构建成功
2. 所有现有测试通过，新增测试覆盖基本渲染
3. 在 `/space` 页面：可创建说说（文字 + 图片）、查看列表、删除、点赞/取消点赞
4. 在 `/space/:userId` 页面：可查看他人公开说说，无创建/删除按钮
5. 侧边栏"个人空间"入口正常高亮
