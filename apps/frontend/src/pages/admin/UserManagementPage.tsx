import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Ban,
  Unlock,
  ShieldCheck,
  Eye,
  Pencil,
  Trash2,
  AlertTriangle,
  Plus,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../../shared/stores/authStore";
import type { UserMe, UserAdminUpdate, UserAdminCreateInput } from "../../shared/api/types";
import { Avatar } from "../../components/ui/Avatar";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";

const roleLabel: Record<UserMe["role"], string> = {
  0: "普通用户",
  1: "VIP",
  2: "管理员",
  3: "超级管理员",
};

const statusLabel: Record<UserMe["status"], string> = {
  0: "正常",
  1: "临时封禁",
  2: "限制中",
  3: "已封禁",
};

const genderLabel: Record<number, string> = {
  0: "未知",
  1: "男",
  2: "女",
};

/** 判断当前登录的管理员是否有权限操作目标用户。
 *
 * 权限规则（与后端保持一致）：
 * - 超级管理员可以管理所有非超级管理员
 * - 超级管理员不能管理其他超级管理员，也不能管理自己
 * - 管理员只能管理普通用户(0)和VIP(1)
 * - 管理员不能管理自己、其他管理员(2)和超级管理员(3)
 */
const canManage = (currentUser: UserMe | null, target: UserMe): boolean => {
  if (!currentUser) return false;
  if (currentUser.role === 3) {
    return target.role < 3 && target.id !== currentUser.id;
  }
  if (currentUser.role === 2) {
    return target.id !== currentUser.id && target.role < 2;
  }
  return false;
};

/** 详情弹窗中的信息行组件。 */
const InfoRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--color-border)" }}>
    <span style={{ color: "var(--color-muted)", fontSize: 13 }}>{label}</span>
    <span style={{ fontSize: 13, fontWeight: 500, textAlign: "right" }}>{value}</span>
  </div>
);

/** 格式化日期时间字符串为本地可读格式。 */
const fmtDate = (s: string | null): string => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString("zh-CN");
};

/** 将天数转换为 ISO 8601 duration 字符串。 */
const daysToDuration = (days: number): string => {
  if (!Number.isFinite(days) || days <= 0) return "";
  return `P${days}D`;
};

export const UserManagementPage = () => {
  const { api, user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<UserMe[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [deletedFilter, setDeletedFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("id");
  const [sortOrder, setSortOrder] = useState<string>("asc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(false);

  // 弹窗状态
  const [viewUser, setViewUser] = useState<UserMe | null>(null);
  const [editUser, setEditUser] = useState<UserMe | null>(null);
  const [banUser, setBanUser] = useState<UserMe | null>(null);
  const [deleteUser, setDeleteUser] = useState<UserMe | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  // 编辑表单
  const [editForm, setEditForm] = useState<UserAdminUpdate>({});
  const [editSubmitting, setEditSubmitting] = useState(false);

  // 创建用户表单
  const [createForm, setCreateForm] = useState<UserAdminCreateInput>({
    username: "",
    nickname: "",
    password: "",
    gender: 0,
    role: 0,
    status: 0,
    safety_score: 10,
    is_verified: false,
    exp: 0,
  });
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // 封禁表单
  const [banStatus, setBanStatus] = useState<1 | 2 | 3>(3);
  const [banDays, setBanDays] = useState<string>("");
  const [banSubmitting, setBanSubmitting] = useState(false);

  // 删除确认
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.adminListUsers({
        q: query || undefined,
        role: roleFilter ? Number(roleFilter) : undefined,
        status: statusFilter ? Number(statusFilter) : undefined,
        isDeleted: deletedFilter === "true" ? true : deletedFilter === "false" ? false : undefined,
        sortBy,
        sortOrder,
        limit: pageSize,
        offset: page * pageSize,
      });
      setUsers(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [api, query, roleFilter, statusFilter, deletedFilter, sortBy, sortOrder, page, pageSize]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleSearch = () => setPage(0);

  const totalPages = Math.ceil(total / pageSize);

  // 打开编辑弹窗时初始化表单
  const openEdit = (user: UserMe) => {
    setEditUser(user);
    setEditForm({
      nickname: user.nickname,
      email: user.email ?? undefined,
      phone: user.phone ?? undefined,
      gender: user.gender,
      birth: user.birth ?? undefined,
      city: user.city ?? undefined,
      bio: user.bio ?? undefined,
      role: user.role,
      is_verified: user.is_verified,
    });
  };

  const handleEditSubmit = async () => {
    if (!editUser) return;
    setEditSubmitting(true);
    try {
      const updated = await api.adminUpdateUser(editUser.id, editForm);
      setUsers((prev) => prev.map((u) => (u.id === editUser.id ? updated : u)));
      toast.success("用户信息已更新");
      setEditUser(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新失败");
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleBan = async () => {
    if (!banUser) return;
    setBanSubmitting(true);
    try {
      const duration = banDays ? daysToDuration(Number(banDays)) : undefined;
      const updated = await api.adminBanUser(banUser.id, banStatus, duration);
      setUsers((prev) => prev.map((u) => (u.id === banUser.id ? updated : u)));
      toast.success("用户已封禁");
      setBanUser(null);
      setBanDays("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "封禁失败");
    } finally {
      setBanSubmitting(false);
    }
  };

  const handleUnban = async (userId: number) => {
    try {
      const updated = await api.adminUnbanUser(userId);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      toast.success("用户已解封");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleDelete = async () => {
    if (!deleteUser || deleteConfirmInput !== deleteUser.username) return;
    setDeleteSubmitting(true);
    try {
      await api.adminDeleteUser(deleteUser.id);
      setUsers((prev) => prev.filter((u) => u.id !== deleteUser.id));
      setTotal((t) => t - 1);
      toast.success("用户已永久删除");
      setDeleteUser(null);
      setDeleteConfirmInput("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleteSubmitting(false);
    }
  };

  const handleCreateSubmit = async () => {
    if (!createForm.username || !createForm.nickname || !createForm.password) return;
    setCreateSubmitting(true);
    try {
      const newUser = await api.adminCreateUser(createForm);
      setUsers((prev) => [newUser, ...prev]);
      setTotal((t) => t + 1);
      toast.success("用户创建成功");
      setCreateModalOpen(false);
      setCreateForm({
        username: "",
        nickname: "",
        password: "",
        gender: 0,
        role: 0,
        status: 0,
        safety_score: 10,
        is_verified: false,
        exp: 0,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreateSubmitting(false);
    }
  };

  /** 根据当前管理员角色返回可创建的角色选项。
   * - 超级管理员可创建所有角色
   * - 普通管理员只能创建普通用户和VIP
   */
  const getCreatableRoles = (): UserMe["role"][] => {
    if (currentUser?.role === 3) return [0, 1, 2, 3];
    return [0, 1];
  };

  return (
    <>
      <PaginatedPageLayout
        header={(
          <>
      <FadeIn>
        <div className="admin-page-header">
          <h1 className="page-title">用户管理</h1>
          <motion.button
            className="primary-button"
            onClick={() => setCreateModalOpen(true)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Plus size={16} />
            创建用户
          </motion.button>
        </div>
      </FadeIn>

      <FadeIn delay={0.08}>
        {/* 搜索栏 */}
        <div className="admin-search-row">
          <div className="admin-search-input-wrap">
            <Search size={14} className="admin-search-icon" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索用户名或昵称..."
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>

          <motion.button
            className="primary-button"
            onClick={handleSearch}
            disabled={loading}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            {loading ? "加载中" : "搜索"}
          </motion.button>
        </div>

        {/* 筛选栏 */}
        <div className="admin-filter-bar">
          <div className="admin-filter-field">
            <select
              value={roleFilter}
              onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
            >
              <option value="">全部角色</option>
              <option value="0">普通用户</option>
              <option value="1">VIP</option>
              <option value="2">管理员</option>
              <option value="3">超级管理员</option>
            </select>
          </div>

          <div className="admin-filter-field">
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            >
              <option value="">全部状态</option>
              <option value="0">正常</option>
              <option value="1">临时封禁</option>
              <option value="2">限制中</option>
              <option value="3">已封禁</option>
            </select>
          </div>

          <div style={{ flex: "1 1 110px", minWidth: 110 }}>
            <select
              value={deletedFilter}
              onChange={(e) => { setDeletedFilter(e.target.value); setPage(0); }}
            >
              <option value="">全部</option>
              <option value="false">未注销</option>
              <option value="true">已注销</option>
            </select>
          </div>

          <div style={{ flex: "1 1 140px", minWidth: 140 }}>
            <select
              value={sortBy}
              onChange={(e) => { setSortBy(e.target.value); setPage(0); }}
            >
              <option value="id">用户ID</option>
              <option value="created_at">注册时间</option>
              <option value="exp">经验值</option>
              <option value="level">等级</option>
              <option value="like_count">获赞数</option>
            </select>
          </div>

          <div style={{ flex: "1 1 110px", minWidth: 110 }}>
            <select
              value={sortOrder}
              onChange={(e) => { setSortOrder(e.target.value); setPage(0); }}
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </div>
        </div>
      </FadeIn>
          </>
        )}
        footer={
          users.length > 0 && (totalPages > 1 || total > 0) ? (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => { setPageSize(size); setPage(0); }}
              loading={loading}
              total={total}
            />
          ) : undefined
        }
      >
      {users.length > 0 ? (
        <FadeIn delay={0.15}>
          <div className="admin-table-container">
            <div
              className="admin-table-header"
              style={{ gridTemplateColumns: "60px 1fr 1fr 100px 100px 80px auto" }}
            >
              <span>ID</span>
              <span>用户名</span>
              <span>昵称</span>
              <span>角色</span>
              <span>状态</span>
              <span>是否注销</span>
              <span>操作</span>
            </div>
            <StaggerContainer staggerDelay={0.03}>
              {users.map((item) => (
                <StaggerItem key={item.id}>
                  <motion.div
                    className="admin-table-row"
                    style={{ gridTemplateColumns: "60px 1fr 1fr 100px 100px 80px auto", alignItems: "center" }}
                    whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                  >
                    <span style={{ fontSize: 12, color: "var(--color-muted)" }}>{item.id}</span>
                    <span style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      @{item.username}
                    </span>
                    <span style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.nickname}
                    </span>
                    <span style={{ fontSize: 13 }}>{roleLabel[item.role]}</span>
                    <span>
                      <span
                        className={`status-badge ${
                          item.is_deleted
                            ? "deleted"
                            : item.status === 0
                              ? "active"
                              : item.status === 3
                                ? "banned"
                                : "temp-ban"
                        }`}
                      >
                        {item.is_deleted ? "已注销" : statusLabel[item.status]}
                      </span>
                    </span>
                    <span style={{ fontSize: 13 }}>
                      {item.is_deleted ? (
                        <span style={{ color: "var(--color-muted)" }}>是</span>
                      ) : (
                        <span style={{ color: "var(--color-accent-2)" }}>否</span>
                      )}
                    </span>
                    <div style={{ display: "flex", gap: 6, alignItems: "center", minWidth: 140 }}>
                      <motion.button
                        className="ghost-button"
                        onClick={() => canManage(currentUser, item) && setViewUser(item)}
                        disabled={!canManage(currentUser, item)}
                        whileHover={canManage(currentUser, item) ? { scale: 1.1 } : {}}
                        whileTap={canManage(currentUser, item) ? { scale: 0.9 } : {}}
                        type="button"
                        title="查看详情"
                        style={{ padding: "6px 8px", minHeight: "auto", opacity: canManage(currentUser, item) ? 1 : 0.2 }}
                      >
                        <Eye size={14} />
                      </motion.button>
                      <motion.button
                        className="ghost-button"
                        onClick={() => canManage(currentUser, item) && openEdit(item)}
                        disabled={!canManage(currentUser, item) || item.is_deleted}
                        whileHover={canManage(currentUser, item) && !item.is_deleted ? { scale: 1.1 } : {}}
                        whileTap={canManage(currentUser, item) && !item.is_deleted ? { scale: 0.9 } : {}}
                        type="button"
                        title="编辑资料"
                        style={{ padding: "6px 8px", minHeight: "auto", opacity: canManage(currentUser, item) && !item.is_deleted ? 1 : 0.2 }}
                      >
                        <Pencil size={14} />
                      </motion.button>
                      <motion.button
                        className="ghost-button"
                        onClick={() => {
                          if (!canManage(currentUser, item) || item.is_deleted) return;
                          if (item.status === 0) {
                            setBanUser(item);
                            setBanStatus(3);
                            setBanDays("");
                          } else {
                            void handleUnban(item.id);
                          }
                        }}
                        disabled={!canManage(currentUser, item) || item.is_deleted}
                        whileHover={canManage(currentUser, item) && !item.is_deleted ? { scale: 1.1 } : {}}
                        whileTap={canManage(currentUser, item) && !item.is_deleted ? { scale: 0.9 } : {}}
                        type="button"
                        title={item.status === 0 ? "封禁" : "解封"}
                        style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-danger)", opacity: canManage(currentUser, item) && !item.is_deleted ? 1 : 0.2 }}
                      >
                        {item.status === 0 ? <Ban size={14} /> : <Unlock size={14} />}
                      </motion.button>
                      <motion.button
                        className="ghost-button"
                        onClick={() => canManage(currentUser, item) && !item.is_deleted && (() => { setDeleteUser(item); setDeleteConfirmInput(""); })()}
                        disabled={!canManage(currentUser, item) || item.is_deleted}
                        whileHover={canManage(currentUser, item) && !item.is_deleted ? { scale: 1.1 } : {}}
                        whileTap={canManage(currentUser, item) && !item.is_deleted ? { scale: 0.9 } : {}}
                        type="button"
                        title="永久删除"
                        style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-danger)", opacity: canManage(currentUser, item) && !item.is_deleted ? 1 : 0.2 }}
                      >
                        <Trash2 size={14} />
                      </motion.button>
                    </div>
                  </motion.div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>
        </FadeIn>
      ) : (
        <FadeIn delay={0.15}>
          <EmptyState
            icon={ShieldCheck}
            title="暂无用户"
            description="未找到符合条件的用户，请调整筛选条件或搜索关键词。"
          />
        </FadeIn>
      )}
      </PaginatedPageLayout>

      {/* 查看详情弹窗 */}
      <Modal
        open={!!viewUser}
        onClose={() => setViewUser(null)}
        title="用户详细资料"
        maxWidth={560}
      >
        {viewUser && (
          <div>
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
              <Avatar user={viewUser} size="xl" />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
              <InfoRow label="用户ID" value={viewUser.id} />
              <InfoRow label="用户名" value={`@${viewUser.username}`} />
              <InfoRow label="昵称" value={viewUser.nickname} />
              <InfoRow label="性别" value={genderLabel[viewUser.gender] ?? "未知"} />
              <InfoRow label="角色" value={roleLabel[viewUser.role]} />
              <InfoRow label="状态" value={
                <span className={`status-badge ${viewUser.status === 0 ? "active" : viewUser.status === 3 ? "banned" : "temp-ban"}`}>
                  {statusLabel[viewUser.status]}
                </span>
              } />
              <InfoRow label="等级" value={`Lv.${viewUser.level}`} />
              <InfoRow label="经验值" value={viewUser.exp} />
              <InfoRow label="安全分" value={viewUser.safety_score} />
              <InfoRow label="是否认证" value={viewUser.is_verified ? "是" : "否"} />
              <InfoRow label="获赞数" value={viewUser.like_count} />
              <InfoRow label="生日" value={viewUser.birth ?? "—"} />
              <InfoRow label="城市" value={viewUser.city ?? "—"} />
            </div>
            <InfoRow label="邮箱" value={viewUser.email ?? "—"} />
            <InfoRow label="手机号" value={viewUser.phone ?? "—"} />
            <InfoRow label="简介" value={viewUser.bio ?? "—"} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px" }}>
              <InfoRow label="注册时间" value={fmtDate(viewUser.created_at)} />
              <InfoRow label="最后登录" value={fmtDate(viewUser.last_login_at)} />
              <InfoRow label="封禁时间" value={fmtDate(viewUser.banned_at)} />
              <InfoRow label="封禁时长" value={viewUser.ban_duration ?? "—"} />
            </div>
          </div>
        )}
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        open={!!editUser}
        onClose={() => setEditUser(null)}
        title="编辑用户资料"
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => setEditUser(null)}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="btn-primary"
              onClick={handleEditSubmit}
              disabled={editSubmitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {editSubmitting ? "保存中..." : "保存"}
            </motion.button>
          </>
        }
      >
        {editUser && (
          <div className="form-stack modal-form-grid">
            <label>
              昵称
              <input
                value={editForm.nickname ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, nickname: e.target.value }))}
                required
              />
            </label>
            <label>
              邮箱
              <input
                type="email"
                value={editForm.email ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value || undefined }))}
              />
            </label>
            <label>
              手机号
              <input
                value={editForm.phone ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value || undefined }))}
              />
            </label>
            <label>
              性别
              <select
                value={String(editForm.gender ?? 0)}
                onChange={(e) => setEditForm((f) => ({ ...f, gender: Number(e.target.value) }))}
              >
                <option value="0">未知</option>
                <option value="1">男</option>
                <option value="2">女</option>
              </select>
            </label>
            <label>
              生日
              <input
                type="date"
                value={editForm.birth ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, birth: e.target.value || undefined }))}
              />
            </label>
            <label>
              城市
              <input
                value={editForm.city ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value || undefined }))}
              />
            </label>
            <label>
              简介
              <textarea
                rows={4}
                value={editForm.bio ?? ""}
                onChange={(e) => setEditForm((f) => ({ ...f, bio: e.target.value || undefined }))}
              />
            </label>
            {currentUser?.role === 3 && (
              <>
                <label>
                  角色
                  <select
                    value={String(editForm.role ?? 0)}
                    onChange={(e) => setEditForm((f) => ({ ...f, role: Number(e.target.value) as UserMe["role"] }))}
                  >
                    <option value="0">普通用户</option>
                    <option value="1">VIP</option>
                    <option value="2">管理员</option>
                    <option value="3">超级管理员</option>
                  </select>
                </label>
              </>
            )}
            <label className="form-checkbox">
              <input
                type="checkbox"
                checked={editForm.is_verified ?? false}
                onChange={(e) => setEditForm((f) => ({ ...f, is_verified: e.target.checked }))}
              />
              <span>已认证</span>
            </label>
          </div>
        )}
      </Modal>

      {/* 封禁弹窗 */}
      <Modal
        open={!!banUser}
        onClose={() => setBanUser(null)}
        title="封禁用户"
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => setBanUser(null)}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="danger-button"
              onClick={handleBan}
              disabled={banSubmitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {banSubmitting ? "处理中..." : "确认封禁"}
            </motion.button>
          </>
        }
      >
        {banUser && (
          <div className="form-stack">
            <p style={{ margin: 0, fontSize: 13, color: "var(--color-muted)" }}>
              即将封禁用户 <strong>@{banUser.username}</strong>，请选择封禁类型和时长。
            </p>
            <label>
              封禁类型
              <select
                value={banStatus}
                onChange={(e) => setBanStatus(Number(e.target.value) as 1 | 2 | 3)}
              >
                <option value={1}>临时封禁</option>
                <option value={2}>限制中</option>
                <option value={3}>已封禁</option>
              </select>
            </label>
            <label>
              封禁时长（天，可选）
              <input
                type="number"
                min={1}
                placeholder="不填则为无限期"
                value={banDays}
                onChange={(e) => setBanDays(e.target.value)}
              />
            </label>
          </div>
        )}
      </Modal>

      {/* 删除确认弹窗 */}
      <Modal
        open={!!deleteUser}
        onClose={() => { setDeleteUser(null); setDeleteConfirmInput(""); }}
        title="永久删除用户"
        maxWidth={460}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => { setDeleteUser(null); setDeleteConfirmInput(""); }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="danger-button"
              onClick={handleDelete}
              disabled={deleteSubmitting || !deleteUser || deleteConfirmInput !== deleteUser.username}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {deleteSubmitting ? "删除中..." : "确认永久删除"}
            </motion.button>
          </>
        }
      >
        {deleteUser && (
          <div className="form-stack">
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "12px 14px",
                background: "rgba(229, 72, 77, 0.08)",
                borderRadius: 10,
                border: "1px solid rgba(229, 72, 77, 0.2)",
              }}
            >
              <AlertTriangle size={20} style={{ color: "var(--color-danger)", flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: "var(--color-danger)" }}>
                危险操作：此操作不可撤销，该用户的所有数据（包括歌单、评论、动态等）将被一并删除。
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "var(--color-muted)" }}>
              请输入用户 <strong>@{deleteUser.username}</strong> 的用户名以确认永久删除。
            </p>
            <label>
              用户名确认
              <input
                value={deleteConfirmInput}
                onChange={(e) => setDeleteConfirmInput(e.target.value)}
                placeholder={`请输入 "${deleteUser.username}"`}
                autoFocus
              />
            </label>
          </div>
        )}
      </Modal>

      {/* 创建用户弹窗 */}
      <Modal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="创建用户"
        maxWidth={560}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => setCreateModalOpen(false)}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="btn-primary"
              onClick={handleCreateSubmit}
              disabled={
                createSubmitting ||
                !createForm.username ||
                !createForm.nickname ||
                !createForm.password
              }
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {createSubmitting ? "创建中..." : "创建用户"}
            </motion.button>
          </>
        }
      >
        <div className="form-stack modal-form-grid">
          <label>
            用户名 *
            <input
              value={createForm.username}
              onChange={(e) => setCreateForm((f) => ({ ...f, username: e.target.value }))}
              placeholder="3-32 位字符"
              required
            />
          </label>
          <label>
            昵称 *
            <input
              value={createForm.nickname}
              onChange={(e) => setCreateForm((f) => ({ ...f, nickname: e.target.value }))}
              placeholder="1-32 位字符"
              required
            />
          </label>
          <label>
            密码 *
            <input
              type="password"
              value={createForm.password}
              onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
              placeholder="至少 6 位"
              required
            />
          </label>
          <label>
            邮箱
            <input
              type="email"
              value={createForm.email ?? ""}
              onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value || undefined }))}
            />
          </label>
          <label>
            手机号
            <input
              value={createForm.phone ?? ""}
              onChange={(e) => setCreateForm((f) => ({ ...f, phone: e.target.value || undefined }))}
            />
          </label>
          <label>
            性别
            <select
              value={String(createForm.gender ?? 0)}
              onChange={(e) => setCreateForm((f) => ({ ...f, gender: Number(e.target.value) }))}
            >
              <option value="0">未知</option>
              <option value="1">男</option>
              <option value="2">女</option>
            </select>
          </label>
          <label>
            生日
            <input
              type="date"
              value={createForm.birth ?? ""}
              onChange={(e) => setCreateForm((f) => ({ ...f, birth: e.target.value || undefined }))}
            />
          </label>
          <label>
            城市
            <input
              value={createForm.city ?? ""}
              onChange={(e) => setCreateForm((f) => ({ ...f, city: e.target.value || undefined }))}
            />
          </label>
          <label>
            简介
            <textarea
              rows={3}
              value={createForm.bio ?? ""}
              onChange={(e) => setCreateForm((f) => ({ ...f, bio: e.target.value || undefined }))}
            />
          </label>
          <label>
            角色
            <select
              value={String(createForm.role ?? 0)}
              onChange={(e) => setCreateForm((f) => ({ ...f, role: Number(e.target.value) as UserMe["role"] }))}
            >
              {getCreatableRoles().map((r) => (
                <option key={r} value={r}>
                  {roleLabel[r]}
                </option>
              ))}
            </select>
          </label>
          <label>
            状态
            <select
              value={String(createForm.status ?? 0)}
              onChange={(e) => setCreateForm((f) => ({ ...f, status: Number(e.target.value) as UserMe["status"] }))}
            >
              <option value="0">正常</option>
              <option value="1">临时封禁</option>
              <option value="2">限制中</option>
              <option value="3">已封禁</option>
            </select>
          </label>
          <label>
            安全分
            <input
              type="number"
              min={0}
              max={10}
              value={createForm.safety_score ?? 10}
              onChange={(e) => setCreateForm((f) => ({ ...f, safety_score: Number(e.target.value) }))}
            />
          </label>
          <label>
            经验值
            <input
              type="number"
              min={0}
              value={createForm.exp ?? 0}
              onChange={(e) => setCreateForm((f) => ({ ...f, exp: Number(e.target.value) }))}
            />
          </label>
          <label className="form-checkbox">
            <input
              type="checkbox"
              checked={createForm.is_verified ?? false}
              onChange={(e) => setCreateForm((f) => ({ ...f, is_verified: e.target.checked }))}
            />
            <span>已认证</span>
          </label>
        </div>
      </Modal>
    </>
  );
};
