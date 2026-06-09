import { useState } from "react";
import { Search, Ban, Unlock, ShieldCheck } from "lucide-react";
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

export const UserManagementPage = () => {
  const { api } = useAuthStore();
  const [users, setUsers] = useState<UserMe[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const list = await api.adminListUsers({ q: query || undefined });
      setUsers(list);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  };

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
        <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
          <div style={{ position: "relative", flex: 1, maxWidth: 320 }}>
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
              placeholder="搜索用户..."
              style={{ paddingLeft: 32 }}
              onKeyDown={(e) => e.key === "Enter" && loadUsers()}
            />
          </div>
          <motion.button
            className="primary-button"
            onClick={loadUsers}
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
                      {item.status === 0 ? (
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
                      )}
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
            title="用户列表"
            description="输入搜索关键词后点击搜索按钮加载用户列表。"
          />
        </FadeIn>
      )}
    </div>
  );
};