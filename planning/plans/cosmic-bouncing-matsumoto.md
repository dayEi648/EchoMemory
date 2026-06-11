# 计划：后端列表查询全部改为分页查询

## 背景

当前后端部分列表查询端点虽然接受 `limit`/`offset` 参数，但返回纯数组（无 `total` 计数），前端无法计算总页数，也就无法实现真正的分页 UI。用户要求以"用户管理"中的分页查询为参考，将所有非分页查询统一改为返回 `{ items, total }` 格式。

## 现状分析

### 已有完整分页的端点（无需修改）

| 端点 | 说明 |
|------|------|
| `GET /users/` | search_users，已返回 `PaginatedUserSearchOut` |
| `GET /users/admin/list` | admin_list_users，已返回 `PaginatedUserAdminOut` |
| `GET /music/search` | search_musics，已返回 `PaginatedMusicListOut` |
| `GET /music/admin/list` | admin_list_music，已返回 `PaginatedAdminMusicListOut` |
| `GET /albums/search` | search_albums，已返回 `PaginatedAlbumListOut` |
| `GET /albums/admin/list` | admin_list_albums，已返回 `PaginatedAdminAlbumListOut` |
| `GET /dictionary/{type}` | list_dictionary_items，已返回 `DictionaryItemListOut` |

### 需要修改的端点

**前端正在使用的：**

| 端点 | 前端使用处 | 当前返回 |
|------|-----------|---------|
| `GET /music/` | DiscoverPage(limit:8), MusicDetailPage(limit:6) | `list[MusicListOut]` |
| `GET /albums/` | DiscoverPage(limit:5) | `list[AlbumListOut]` |
| `GET /play-history/` | DiscoverPage(limit:5), HistoryPage(limit:50) | `list[PlayHistoryOut]` |

**前端尚未使用（仅后端修改）：**

| 端点 | 当前返回 |
|------|---------|
| `GET /playlists/` | `list[PlaylistListOut]` |
| `GET /comments/{type}/{id}` | `list[CommentOut]` |
| `GET /collections/musics` | `list[MusicCollectionOut]` |
| `GET /collections/albums` | `list[AlbumCollectionOut]` |
| `GET /collections/playlists` | `list[PlaylistCollectionOut]` |
| `GET /collections/releases` | `list[ReleaseOut]` |
| `GET /space-posts/` | `list[SpacePostListOut]` |
| `GET /users/{id}/followees` | `list[FolloweeOut]` |
| `GET /users/{id}/followers` | `list[FollowerOut]` |

### 不需要修改的端点

| 端点 | 原因 |
|------|------|
| `GET /users/me/emotion-tags` | 标签数量有限（固定11个），不需要分页 |
| `GET /users/me/interest-tags` | 标签数量有限（固定12个），不需要分页 |

## 修改方案

### 模式（参考已有实现）

每个列表查询统一改为以下模式：

1. **服务层**：函数返回类型从 `list[Model]` 改为 `dict[str, object]`，同时执行数据查询和 `func.count()` 总计数查询
2. **Schema 层**：新增 `PaginatedXxxOut`（`items: list[XxxOut]`, `total: int`）
3. **端点层**：`response_model` 从 `list[XxxOut]` 改为 `PaginatedXxxOut`

### 后端修改清单

#### 服务层（12个函数）

| 函数 | 文件 | 修改 |
|------|------|------|
| `list_musics` | `services/music_service.py` | 添加 total 查询，返回 dict |
| `list_albums` | `services/album_service.py` | 添加 total 查询，返回 dict |
| `list_user_playlists` | `services/playlist_service.py` | 添加 total 查询，返回 dict |
| `list_comments` | `services/comment_service.py` | 添加 total 查询，返回 dict |
| `list_music_collections` | `services/collection_service.py` | 添加 total 查询，返回 dict |
| `list_album_collections` | `services/collection_service.py` | 添加 total 查询，返回 dict |
| `list_playlist_collections` | `services/collection_service.py` | 添加 total 查询，返回 dict |
| `list_releases` | `services/collection_service.py` | 添加 total 查询，返回 dict |
| `list_play_history` | `services/play_history_service.py` | 添加 total 查询，返回 dict |
| `list_space_posts` | `services/space_post_service.py` | 添加 total 查询，返回 dict |
| `get_followees` | `services/user_service.py` | 添加 total 查询，返回 dict |
| `get_followers` | `services/user_service.py` | 添加 total 查询，返回 dict |

#### Schema 层（10个新增）

| Schema | 文件 |
|--------|------|
| `PaginatedPlaylistListOut` | `schemas/playlist.py` |
| `PaginatedCommentOut` | `schemas/comment.py` |
| `PaginatedMusicCollectionOut` | `schemas/collection.py` |
| `PaginatedAlbumCollectionOut` | `schemas/collection.py` |
| `PaginatedPlaylistCollectionOut` | `schemas/collection.py` |
| `PaginatedReleaseOut` | `schemas/collection.py` |
| `PaginatedPlayHistoryOut` | `schemas/play_history.py` |
| `PaginatedSpacePostListOut` | `schemas/space_post.py` |
| `PaginatedFolloweeOut` | `schemas/user.py` |
| `PaginatedFollowerOut` | `schemas/user.py` |

已有但端点未使用的：
- `PaginatedMusicListOut`（已存在，但 `list_musics` 端点未使用）→ 直接复用
- `PaginatedAlbumListOut`（已存在，但 `list_albums` 端点未使用）→ 直接复用

#### 端点层（12个端点）

修改各端点的 `response_model`，与服务层和 Schema 对应：

| 端点 | 文件 | 新 response_model |
|------|------|------------------|
| `GET /music/` | `endpoints/music.py` | `PaginatedMusicListOut` |
| `GET /albums/` | `endpoints/album.py` | `PaginatedAlbumListOut` |
| `GET /playlists/` | `endpoints/playlist.py` | `PaginatedPlaylistListOut` |
| `GET /comments/{type}/{id}` | `endpoints/comment.py` | `PaginatedCommentOut` |
| `GET /collections/musics` | `endpoints/collection.py` | `PaginatedMusicCollectionOut` |
| `GET /collections/albums` | `endpoints/collection.py` | `PaginatedAlbumCollectionOut` |
| `GET /collections/playlists` | `endpoints/collection.py` | `PaginatedPlaylistCollectionOut` |
| `GET /collections/releases` | `endpoints/collection.py` | `PaginatedReleaseOut` |
| `GET /play-history/` | `endpoints/play_history.py` | `PaginatedPlayHistoryOut` |
| `GET /space-posts/` | `endpoints/space_post.py` | `PaginatedSpacePostListOut` |
| `GET /users/{id}/followees` | `endpoints/users.py` | `PaginatedFolloweeOut` |
| `GET /users/{id}/followers` | `endpoints/users.py` | `PaginatedFollowerOut` |

### 前端修改清单

#### API 层（3个文件）

| 文件 | 修改 |
|------|------|
| `shared/api/musicApi.ts` | `listMusic` 返回类型改为 `PaginatedMusicList` |
| `shared/api/albumApi.ts` | `listAlbums` 返回类型改为 `PaginatedAlbumList` |
| `shared/api/playHistoryApi.ts` | `listPlayHistory` 返回类型改为 `PaginatedPlayHistoryList`（新增类型） |

#### 页面层

| 文件 | 修改 |
|------|------|
| `pages/DiscoverPage.tsx` | `listMusic`/`listAlbums`/`listPlayHistory` 结果取 `.items`，展示逻辑不变 |
| `pages/HistoryPage.tsx` | 1. `listPlayHistory` 结果取 `.items` 和 `.total`<br>2. 添加 `page`/`pageSize` state 和 PaginationBar<br>3. 实现分页加载 |
| `pages/MusicDetailPage.tsx` | `listMusic` 结果取 `.items`，展示逻辑不变 |

### 不引入 BUG 的保障措施

1. **DiscoverPage** 和 **MusicDetailPage** 使用小量 `limit` 做预览展示，改成分页返回格式后，它们只需要从 `.items` 取数据，展示逻辑完全不变。
2. **HistoryPage** 是唯一需要真正使用分页 UI 的页面，当前它一次性加载 50 条，改成分页后用户体验更好。
3. 前端未使用的 API（playlist, comment, collection, space_post, followees, followers）只改后端，不影响现有功能。
4. 所有修改遵循已有模式（参考 `search_musics` / `search_albums` / `search_users`），代码结构保持一致。
5. 不修改 `limit`/`offset` 的默认值，保持向后兼容。

## 验证

1. 后端启动成功，OpenAPI 文档中各列表端点的响应模型正确显示为分页格式。
2. DiscoverPage 正常加载，新歌上架/推荐专辑/最近播放区域正常显示。
3. MusicDetailPage 正常加载，相关推荐正常显示。
4. HistoryPage 分页功能正常，上一页/下一页/页码切换工作正常。
