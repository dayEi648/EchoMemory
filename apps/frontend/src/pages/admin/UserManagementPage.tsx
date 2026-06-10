import { useEffect, useState, useCallback } from "react";
import { Search, Ban, Unlock, ShieldCheck, ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { useAuthStore } from "../../shared/stores/authStore";
import type { UserMe } from "../../shared/api/types";
import { Avatar } from "../../components/ui/Avatar";
import { EmptyState } from "../../components/ui/EmptyState";
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

/** 判断当前登录的管理员是否有权限操作目标用户。
 *
 * 权限规则：
 * - 超级管理员可以管理自己以及所有非超级管理员
 * - 超级管理员不能管理其他超级管理员
 * - 管理员只能管理普通用户(0)和VIP(1)
 * - 管理员不能管理自己、其他管理员(2)和超级管理员(3)
 */
const canManage = (currentUser: UserMe | null, target: UserMe): boolean => {
  if (!currentUser) return false;
  // 超级管理员可以管理自己以及任何非超级管理员
  if (currentUser.role === 3) {
    return target.role < 3 || target.id === currentUser.id;
  }
  // 管理员只能管理 role < 2 的用户（不能管理自己）
  if (currentUser.role === 2) {
    return target.id !== currentUser.id && target.role < 2;
  }
  return false;
};

export const UserManagementPage = () => {
  const { api, user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<UserMe[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.adminListUsers({
        q: query || undefined,
        role: roleFilter ? Number(roleFilter) : undefined,
        status: statusFilter ? Number(statusFilter) : undefined,
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
  }, [api, query, roleFilter, statusFilter, sortBy, sortOrder, page, pageSize]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleSearch = () => {
    setPage(0);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const totalPages = Math.ceil(total / pageSize);

  const handleBan = async (userId: number) => {
    try {
      const updated = await api.adminBanUser(userId, 3);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
      toast.success("用户已封禁");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
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
                          item.status === 0
                            ? "active"
                            : item.status === 3
                              ? "banned"
                              : "temp-ban"
                        }`}
                      >
                        {statusLabel[item.status]}
                      </span>
                    </span>
                    <span style={{ fontSize: 13 }}>Lv.{item.level}</span>
                    <div>
                      {canManage(currentUser, item) ? (
                        item.status === 0 ? (
                          <motion.button
                            className="danger-button"
                            onClick={() => handleBan(item.id)}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            type="button"
                          >
                            <Ban size={14} />
                            封禁
                          </motion.button>
                        ) : (
                          <motion.button
                            className="ghost-button"
                            onClick={() => handleUnban(item.id)}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            type="button"
                          >
                            <Unlock size={14} />
                            解封
                          </motion.button>
                        )
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
            <div className="pagination-bar">
              <div className="pagination-left">
                <span className="pagination-label">每页</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
                  className="pagination-size-select"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
                <span className="pagination-label">条</span>
              </div>

              <div className="pagination-center">
                <motion.button
                  className="pagination-btn"
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page === 0 || loading}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                >
                  <ChevronLeft size={16} />
                </motion.button>

                {Array.from({ length: totalPages }, (_, i) => i).map((p) => (
                  <motion.button
                    key={p}
                    className={`pagination-btn ${p === page ? "active" : ""}`}
                    onClick={() => handlePageChange(p)}
                    disabled={loading}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                  >
                    {p + 1}
                  </motion.button>
                ))}

                <motion.button
                  className="pagination-btn"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= totalPages - 1 || loading}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                >
                  <ChevronRight size={16} />
                </motion.button>
              </div>

              <span className="pagination-info">
                第 {page + 1} / {totalPages} 页，共 {total} 条
              </span>
            </div>
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
    </div>
  );
};
