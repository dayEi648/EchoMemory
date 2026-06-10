# 用户管理功能增强计划

## 背景与目标

当前管理后台的"用户管理"界面功能过于单薄：表格中每行用户仅有一个"封禁/解封"按钮，且封禁时固定使用 `status=3`（永久封禁），无法选择不同程度的封禁类型（禁言/限制/封禁）。管理员无法查看用户完整资料、无法编辑用户资料、也无法删除用户账号。

本计划旨在为管理后台用户管理页面增加以下能力：
1. **查看用户详细资料** — 弹窗展示用户的完整字段（含敏感字段如 email、phone、status、safety_score 等）。
2. **编辑用户详细资料** — 弹窗表单，支持修改用户的基本信息字段。
3. **支持不同程度的封禁** — 封禁弹窗支持选择封禁类型（临时封禁/限制中/已封禁）和封禁时长。
4. **硬删除用户** — 新增后端接口和前端确认弹窗，弹窗要求管理员手动输入目标用户的用户名以确认删除。

## 现状确认

### 后端已有接口
- `GET /users/admin/list` — 分页用户列表
- `PATCH /users/{user_id}/admin` — 管理员更新用户（支持 role/status/safety_score/is_verified/exp/banned_at/ban_duration）
- `POST /users/{user_id}/ban` — 封禁（支持 status 1/2/3 和可选 ban_duration）
- `POST /users/{user_id}/unban` — 解封

### 后端缺失接口
- 管理员获取单个用户**完整**信息（现有 `GET /users/{user_id}` 返回 `UserPublicOut`，不含 email/phone/status/safety_score 等敏感字段）
- 硬删除用户（需求文档原表述"暂不考虑"，现按用户要求新增）

### 数据库约束
- 所有引用 `users.id` 的外键均为 `ON DELETE CASCADE`，硬删除用户时数据库会自动级联删除其歌单、评论、动态、播放历史、关注关系、收藏等全部关联数据，技术上无阻碍。
- 用户表有 `is_deleted` 软删除字段，但硬删除需求明确。

### 前端组件现状
- 无 Modal/Dialog/Drawer 通用组件，需自建简单弹窗。
- 表单使用原生 HTML 元素 + `.form-stack` / `.form-panel` CSS 类。
- 按钮样式类：`primary-button`、`ghost-button`、`danger-button`。

---

## 实现方案

### 一、后端修改

#### 1.1 扩展 `UserAdminUpdate` Schema（`schemas/user.py`）

现有 `UserAdminUpdate` 只支持 role/status/safety_score/is_verified/exp/banned_at/ban_duration，需扩展以支持管理员编辑用户基本资料：

新增可选字段：
- `nickname: str | None` — 昵称，min_length=1, max_length=32
- `email: EmailStr | None`
- `phone: str | None` — max_length=20
- `gender: Literal[0, 1, 2] | None`
- `birth: date | None`
- `bio: str | None` — max_length=500
- `city: str | None` — max_length=50

#### 1.2 更新 `update_user_as_admin` 服务函数（`admin_service.py`）

在现有逻辑基础上，增加对 nickname/email/phone/gender/birth/bio/city 字段的处理：
- 若修改了 email，需检查新邮箱是否已被占用（同 `update_user_profile` 中的逻辑）。
- 若修改了 phone，需检查新手机号是否已被占用。
- 其他字段直接赋值。

#### 1.3 新增硬删除服务函数（`admin_service.py`）

新增 `hard_delete_user(db, admin, target_user_id)`：
- 调用 `get_user_by_id` 获取目标用户，不存在或已软删除则 404。
- 调用 `_assert_can_manage(admin, user)` 验证权限。
- 执行 `await db.delete(user)` + `await db.commit()`，由数据库 CASCADE 自动清理关联数据。

#### 1.4 新增管理员获取单个用户完整信息服务函数（`admin_service.py`）

新增 `get_user_full(db, admin, target_user_id)`：
- 获取目标用户，不存在或已软删除则 404。
- 调用 `_assert_can_manage(admin, user)` 验证权限。
- 返回用户实例。

#### 1.5 新增两个 API 端点（`users.py`）

- `GET /users/{user_id}/admin` — 返回 `UserMeOut`，供管理员查看单个用户完整资料。
- `DELETE /users/{user_id}/admin` — 无响应体（204），执行硬删除。

### 二、前端修改

#### 2.1 同步扩展前端类型并新增 API 方法（`types.ts` + `userApi.ts`）

- `UserAdminUpdate` 类型扩展：新增 `nickname/email/phone/gender/birth/bio/city` 可选字段，与后端 Schema 保持一致。
- `adminGetUserFull(userId: number)` → `GET /users/{userId}/admin`
- `adminDeleteUser(userId: number)` → `DELETE /users/{userId}/admin`

#### 2.2 新建通用 Modal 组件（`components/ui/Modal.tsx`）

自建一个简洁的 Modal 组件：
- `position: fixed` 全屏遮罩层，`backdrop-filter: blur(4px)`，`background: rgba(0,0,0,0.3)`
- 居中白色内容面板，复用项目现有的圆角（12px）、边框（`var(--color-border)`）风格
- Props: `open: boolean`, `onClose: () => void`, `title: string`, `children: ReactNode`, `footer?: ReactNode`
- 点击遮罩层关闭，按 ESC 关闭
- 使用 Framer Motion `AnimatePresence` 实现淡入淡出动画

#### 2.3 重构 `UserManagementPage.tsx`

操作列按钮组重新设计（在 `canManage` 权限范围内）：

**操作按钮布局：** 改为图标按钮组，节省横向空间：
- 👁 查看详情 — 打开详情弹窗
- ✏ 编辑 — 打开编辑弹窗
- 🔒 封禁/解封 — 根据当前状态显示"封禁"或"解封"
- 🗑 删除 — 危险操作，红色图标

**详情弹窗（View Modal）：**
- 只读展示用户所有字段：ID、用户名、昵称、邮箱、手机号、性别、生日、城市、简介、角色、状态、等级、经验值、安全分、是否认证、获赞数、注册时间、最后登录时间、封禁时间、封禁时长
- 使用两列网格布局，标签+值的形式
- 头像居中展示

**编辑弹窗（Edit Modal）：**
- 表单字段：昵称、邮箱、手机号、性别（下拉）、生日、城市、简介（textarea）
- 复用 `AccountPage.tsx` 中已有的字段和模式
- 提交调用 `api.adminUpdateUser(userId, input)`
- 成功后刷新列表并关闭弹窗

**封禁弹窗（Ban Modal）：**
- 封禁类型选择（单选）：临时封禁（1）/ 限制中（2）/ 已封禁（3）
- 封禁时长输入（可选）：输入天数，后端转换为 ISO 8601 duration 字符串（如 `P7D`）
- 提交调用 `api.adminBanUser(userId, status, duration)`

**硬删除确认弹窗（Delete Modal）：**
- 顶部红色警告图标 + "危险操作"提示
- 显示提示文字："请输入用户 **@{username}** 的用户名以确认永久删除。此操作不可撤销，该用户的所有数据（包括歌单、评论、动态等）将被一并删除。"
- 输入框要求管理员输入目标用户的用户名
- 仅当输入框内容**完全匹配**目标用户 `username` 时，删除按钮才可用
- 删除按钮为 `danger-button`，文字为"确认永久删除"
- 提交调用 `api.adminDeleteUser(userId)`，成功后从列表移除该用户并 toast 提示

---

## 关键文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `apps/backend/src/echomemory_backend/schemas/user.py` | 修改 | 扩展 `UserAdminUpdate` 字段 |
| `apps/backend/src/echomemory_backend/services/admin_service.py` | 修改 | 扩展 `update_user_as_admin`、新增 `hard_delete_user`、`get_user_full` |
| `apps/backend/src/echomemory_backend/api/v1/endpoints/users.py` | 修改 | 新增 `GET /{user_id}/admin`、`DELETE /{user_id}/admin` |
| `apps/frontend/src/shared/api/types.ts` | 修改 | 扩展 `UserAdminUpdate` 类型 |
| `apps/frontend/src/shared/api/userApi.ts` | 修改 | 新增 `adminGetUserFull`、`adminDeleteUser` |
| `apps/frontend/src/components/ui/Modal.tsx` | 新增 | 通用弹窗组件 |
| `apps/frontend/src/pages/admin/UserManagementPage.tsx` | 大幅修改 | 重构操作列、新增 4 个弹窗状态 |

---

## 验证方案

1. **后端编译**：`cd apps/backend && python -m py_compile src/echomemory_backend/services/admin_service.py src/echomemory_backend/api/v1/endpoints/users.py`
2. **前端编译**：`cd apps/frontend && npx tsc --noEmit`（检查 TypeScript 类型）
3. **手动验证**：
   - 启动前后端服务
   - 以管理员身份登录管理后台 `/admin/users`
   - 点击"查看详情"按钮，确认弹窗正确展示完整用户信息
   - 点击"编辑"按钮，修改用户昵称/城市等，提交后列表刷新
   - 点击"封禁"按钮，选择"限制中"和 7 天，提交后用户状态变为"限制中"
   - 点击"删除"按钮，输入错误的用户名确认按钮不可用，输入正确的用户名后删除成功，列表中该用户消失
