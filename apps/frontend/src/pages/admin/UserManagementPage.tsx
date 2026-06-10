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
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../../shared/stores/authStore";
import type { UserMe, UserAdminUpdate } from "../../shared/api/types";
import { Avatar } from "../../components/ui/Avatar";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
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
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(false);

  // 弹窗状态
  const [viewUser, setViewUser] = useState<UserMe | null>(null);
  const [editUser, setEditUser] = useState<UserMe | null>(null);
  const [banUser, setBanUser] = useState<UserMe | null>(null);
  const [deleteUser, setDeleteUser] = useState<UserMe | null>(null);

  // 编辑表单
  const [editForm, setEditForm] = useState<UserAdminUpdate>({});
  const [editSubmitting, setEditSubmitting] = useState(false);

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

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">用户管理</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ position: "relative", flex: 1, maxWidth: 280 }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--color-muted)",
              }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索用户名或昵称..."
              style={{ paddingLeft: 32 }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>

          <select
            value={roleFilter}
            onChange={(e) => { setRoleFilter(e.target.value); setPage(0); }}
            style={{ width: 130, fontSize: 13 }}
          >
            <option value="">全部角色</option>
            <option value="0">普通用户</option>
            <option value="1">VIP</option>
            <option value="2">管理员</option>
            <option value="3">超级管理员</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            style={{ width: 130, fontSize: 13 }}
          >
            <option value="">全部状态</option>
            <option value="0">正常</option>
            <option value="1">临时封禁</option>
            <option value="2">限制中</option>
            <option value="3">已封禁</option>
          </select>

          <select
            value={deletedFilter}
            onChange={(e) => { setDeletedFilter(e.target.value); setPage(0); }}
            style={{ width: 110, fontSize: 13 }}
          >
            <option value="">全部</option>
            <option value="false">未注销</option>
            <option value="true">已注销</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); setPage(0); }}
            style={{ width: 140, fontSize: 13 }}
          >
            <option value="created_at">注册时间</option>
            <option value="exp">经验值</option>
            <option value="level">等级</option>
            <option value="like_count">获赞数</option>
          </select>

          <select
            value={sortOrder}
            onChange={(e) => { setSortOrder(e.target.value); setPage(0); }}
            style={{ width: 110, fontSize: 13 }}
          >
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </select>

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
      </FadeIn>

      {users.length > 0 ? (
        <FadeIn delay={0.15}>
          <div className="admin-table-container">
            <div
              className="admin-table-header"
              style={{ gridTemplateColumns: "40px 1.2fr 0.8fr 0.8fr 0.7fr auto" }}
            >
              <span></span>
              <span>用户</span>
              <span>角色</span>
              <span>状态</span>
              <span>等级</span>
              <span>操作</span>
            </div>
            <StaggerContainer staggerDelay={0.03}>
              {users.map((item) => (
                <StaggerItem key={item.id}>
                  <motion.div
                    className="admin-table-row"
                    style={{ gridTemplateColumns: "40px 1.2fr 0.8fr 0.8fr 0.7fr auto" }}
                    whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                  >
                    <Avatar user={item} size="sm" />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{item.nickname}</div>
                      <div style={{ fontSize: 12, color: "var(--color-muted)" }}>@{item.username}</div>
                    </div>
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
                    <span style={{ fontSize: 13 }}>Lv.{item.level}</span>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {canManage(currentUser, item) ? (
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <motion.button
                            className="ghost-button"
                            onClick={() => setViewUser(item)}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            type="button"
                            title="查看详情"
                            style={{ padding: "6px 8px", minHeight: "auto" }}
                          >
                            <Eye size={14} />
                          </motion.button>
                          {!item.is_deleted && (
                            <>
                              <motion.button
                                className="ghost-button"
                                onClick={() => openEdit(item)}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                type="button"
                                title="编辑资料"
                                style={{ padding: "6px 8px", minHeight: "auto" }}
                              >
                                <Pencil size={14} />
                              </motion.button>
                              {item.status === 0 ? (
                                <motion.button
                                  className="ghost-button"
                                  onClick={() => { setBanUser(item); setBanStatus(3); setBanDays(""); }}
                                  whileHover={{ scale: 1.1 }}
                                  whileTap={{ scale: 0.9 }}
                                  type="button"
                                  title="封禁"
                                  style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-danger)" }}
                                >
                                  <Ban size={14} />
                                </motion.button>
                              ) : (
                                <motion.button
                                  className="ghost-button"
                                  onClick={() => handleUnban(item.id)}
                                  whileHover={{ scale: 1.1 }}
                                  whileTap={{ scale: 0.9 }}
                                  type="button"
                                  title="解封"
                                  style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-accent-2)" }}
                                >
                                  <Unlock size={14} />
                                </motion.button>
                              )}
                              <motion.button
                                className="ghost-button"
                                onClick={() => { setDeleteUser(item); setDeleteConfirmInput(""); }}
                                whileHover={{ scale: 1.1 }}
                                whileTap={{ scale: 0.9 }}
                                type="button"
                                title="永久删除"
                                style={{ padding: "6px 8px", minHeight: "auto", color: "var(--color-danger)" }}
                              >
                                <Trash2 size={14} />
                              </motion.button>
                            </>
                          )}
                        </div>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--color-muted)" }}>—</span>
                      )}
                    </div>
                  </motion.div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>

          {(totalPages > 1 || total > 0) && (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => { setPageSize(size); setPage(0); }}
              loading={loading}
              total={total}
            />
          )}
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
              className="primary-button"
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
          <div className="form-stack">
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
    </div>
  );
};
