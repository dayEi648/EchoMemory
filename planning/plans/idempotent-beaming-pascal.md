# 用户管理界面功能扩展计划

## 背景

当前管理后台的"用户管理"页面仅支持"封禁/解封"单一操作，缺少查看详情、编辑资料、不同程度的封禁（禁言/限制/封禁）、软删除（注销）、硬删除等管理功能。

## 目标

为用户管理页面添加以下功能：
1. **查看详细资料**：弹窗展示用户所有字段（含敏感信息）
2. **不同程度的封禁**：弹窗选择禁言(TEMP_BAN=1)/限制(SUSPENDED=2)/封禁(BANNED=3)，支持设置封禁时长
3. **编辑详细资料**：弹窗表单，可修改管理字段（role/status/exp/safety_score/is_verified）和基础信息（nickname/email/phone/gender/birth/bio/city）
4. **软删除（注销）**：标记用户 is_deleted=true，数据保留但不可见
5. **硬删除**：从数据库彻底删除用户记录，弹窗要求手动输入用户名确认，级联清理关联数据和 OSS 头像

## 现状分析

### 后端现状
- 已有 `admin_list_users`、`admin_update_user`（PATCH）、`admin_ban_user`（POST）、`admin_unban_user`（POST）
- **没有删除接口**（软删除和硬删除都没有）
- `UserAdminUpdate` schema 只支持 role/status/safety_score/is_verified/exp/banned_at/ban_duration，**不支持基础信息**
- User 模型有 `is_deleted` 软删除字段，但没有任何代码使用它
- 所有外键均设置了 `ondelete="CASCADE"`，数据库会自动级联删除关联记录
- space_post 已有硬删除参考实现模式

### 前端现状
- UserManagementPage.tsx 只有封禁/解封按钮，无弹窗/对话框
- 已有 `adminUpdateUser` API 但未在前端使用
- 项目中没有使用任何 UI 组件库（shadcn/headless/radix 等），全部自定义
- 使用 sonner 做 toast 通知
- 使用 framer-motion 做动画

## 后端修改

### 1. schemas/user.py — 扩展 UserAdminUpdate
新增基础信息字段到 `UserAdminUpdate`：
```python
class UserAdminUpdate(BaseModel):
    role: Literal[0, 1, 2, 3] | None = None
    status: Literal[0, 1, 2, 3] | None = None
    safety_score: int | None = Field(None, ge=0, le=10)
    is_verified: bool | None = None
    exp: int | None = Field(None, ge=0)
    banned_at: datetime | None = None
    ban_duration: str | None = None
    # 新增基础信息字段
    nickname: str | None = Field(None, min_length=1, max_length=32)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    gender: int | None = Field(None, ge=0, le=2)
    birth: date | None = None
    bio: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=50)
```

### 2. services/admin_service.py — 扩展 update_user_as_admin + 新增删除
- `update_user_as_admin` 增加基础字段处理（nickname/email/phone/gender/birth/bio/city）
- 新增 `soft_delete_user(db, admin, target_user_id)` → 设置 is_deleted=true，递增 token version
- 新增 `hard_delete_user(db, admin, target_user_id)` → 先删除 OSS 头像，再 `await db.delete(user)`，数据库 CASCADE 自动清理关联记录

### 3. api/v1/endpoints/users.py — 新增删除路由
- `POST /users/{user_id}/soft-delete` → soft_delete_user（响应 204）
- `DELETE /users/{user_id}` → hard_delete_user（响应 204）

### 4. tests/test_users.py — 新增测试
- 测试管理员编辑用户基础信息
- 测试管理员软删除用户
- 测试管理员硬删除用户
- 测试硬删除时输入用户名确认（这个在前端实现，后端只需要接收 DELETE 请求即可）
- 测试权限边界（管理员不能软删除/硬删除自己/其他管理员/超级管理员）

## 前端修改

### 5. shared/api/userApi.ts — 新增 API 方法
```typescript
adminSoftDeleteUser: (userId: number) => request<void>(`/users/${userId}/soft-delete`, { method: "POST" })
adminHardDeleteUser: (userId: number) => request<void>(`/users/${userId}`, { method: "DELETE" })
```

### 6. pages/admin/UserManagementPage.tsx — 全面重构
在表格操作列增加以下按钮（有权限时才显示）：
- **查看详情**：点击弹出详情面板（全字段只读展示）
- **编辑资料**：点击弹出编辑表单弹窗（支持管理字段+基础信息）
- **封禁**：点击弹出封禁级别选择弹窗（status: 1=临时封禁/2=限制/3=封禁，可选 ban_duration）
- **解封**：直接解封（已有功能保留）
- **软删除**：点击弹出确认弹窗，确认后注销用户
- **硬删除**：点击弹出危险确认弹窗，要求管理员手动输入该用户的 username，匹配后才允许删除

弹窗组件全部内联在页面中实现（不新增独立组件文件），使用 framer-motion 做进入/退出动画。

### 7. index.css — 新增弹窗样式
```css
.modal-overlay { /* 半透明遮罩层 */ }
.modal-panel { /* 白色弹窗面板，居中，圆角 */ }
.modal-header { /* 弹窗标题栏 */ }
.modal-body { /* 弹窗内容区，滚动 */ }
.modal-footer { /* 弹窗底部按钮区 */ }
.danger-modal-title { /* 危险操作弹窗标题（红色）*/ }
```

## 前端弹窗设计

### 详情弹窗
- 两列布局展示所有 UserMe 字段
- 左侧：头像大图 + 状态徽章
- 右侧：字段列表（id, username, nickname, email, phone, role, status, level, exp, safety_score, gender, birth, city, bio, is_verified, like_count, created_at, last_login_at, banned_at, ban_duration）
- 底部：关闭按钮

### 编辑弹窗
- 表单布局，分"基础信息"和"管理设置"两组
- 基础信息：nickname, email, phone, gender(select), birth(date), city, bio(textarea)
- 管理设置：role(select), status(select), exp(number), safety_score(number 0-10), is_verified(checkbox)
- 底部：保存 + 取消

### 封禁弹窗
- 封禁级别选择（radio 或 segmented control）：临时封禁(1) / 限制(2) / 封禁(3)
- 封禁时长（可选输入）：天数或 ISO 8601 格式
- 底部：确认封禁 + 取消

### 硬删除弹窗
- 警告标题（红色）+ 说明文字
- 输入框要求输入：`请输入要删除的用户名 "${username}" 以确认`
- 确认按钮只有在输入完全匹配 username 时才可点击
- 底部：确认删除（红色 danger-button，disabled 直到输入正确）+ 取消

## 验证步骤

1. 后端：`python -m pytest tests/test_users.py -v` → 全部通过
2. 前端：`npx tsc --noEmit && npx vitest run` → 全部通过
3. 联调：启动前后端，实际测试各功能是否正常

## 关键文件列表

| 文件 | 修改类型 |
|------|----------|
| apps/backend/src/echomemory_backend/schemas/user.py | 扩展 UserAdminUpdate |
| apps/backend/src/echomemory_backend/services/admin_service.py | 扩展 update + 新增删除函数 |
| apps/backend/src/echomemory_backend/api/v1/endpoints/users.py | 新增删除路由 |
| apps/backend/tests/test_users.py | 新增测试 |
| apps/frontend/src/shared/api/userApi.ts | 新增 API 方法 |
| apps/frontend/src/pages/admin/UserManagementPage.tsx | 全面重构 |
| apps/frontend/src/index.css | 新增弹窗样式 |
