import { useEffect, useState } from "react";
import { Activity, Users, Music, Album, MessageCircle, FileText, ListMusic } from "lucide-react";
import { motion } from "framer-motion";

import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";
import { userApi } from "../../shared/api/instances";

type DashboardStats = {
  users: number;
  music: number;
  albums: number;
  playlists: number;
  comments: number;
  space_posts: number;
};

const statCards = [
  { key: "users", label: "注册用户", icon: Users, accent: "lavender" as const },
  { key: "music", label: "已上架音乐", icon: Music, accent: "teal" as const },
  { key: "albums", label: "专辑", icon: Album, accent: "coral" as const },
  { key: "playlists", label: "歌单", icon: ListMusic, accent: "ochre" as const },
  { key: "comments", label: "评论", icon: MessageCircle, accent: "pink" as const },
  { key: "space_posts", label: "空间动态", icon: FileText, accent: "lavender" as const },
];

const accentClasses: Record<string, string> = {
  lavender: "dashboard-stat-card dashboard-stat-card--lavender",
  teal: "dashboard-stat-card dashboard-stat-card--teal",
  coral: "dashboard-stat-card dashboard-stat-card--coral",
  ochre: "dashboard-stat-card dashboard-stat-card--ochre",
  pink: "dashboard-stat-card dashboard-stat-card--pink",
};

export const AdminDashboardPage = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    userApi.adminGetStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">管理概览</h1>
      </FadeIn>

      <StaggerContainer staggerDelay={0.08} className="admin-stats-grid">
        {statCards.map((card) => (
          <StaggerItem key={card.key}>
            <motion.div
              className={accentClasses[card.accent]}
              whileHover={{ y: -4, scale: 1.01 }}
              transition={{ duration: 0.25 }}
            >
              <motion.div
                className="stat-card-icon"
                whileHover={{ rotate: [0, -5, 5, 0] }}
                transition={{ duration: 0.4 }}
              >
                <card.icon size={18} />
              </motion.div>
              <div className="stat-value">
                {stats ? (stats[card.key as keyof DashboardStats] ?? 0).toLocaleString() : "—"}
              </div>
              <div className="stat-label">{card.label}</div>
            </motion.div>
          </StaggerItem>
        ))}
      </StaggerContainer>

      <FadeIn delay={0.35}>
        <section>
          <div className="section-header">
            <h3>系统状态</h3>
          </div>
          <motion.div
            className="warm-panel"
            whileHover={{ boxShadow: "0 4px 16px color-mix(in srgb, var(--color-brand-ochre) 12%, transparent)" }}
            transition={{ duration: 0.25 }}
          >
            <p className="panel-muted-text">
              热度定时维护每 4 小时执行一次；播放、收藏、评论时自动更新单首歌曲热度。
              转发功能已上线，用户可将音乐、专辑、歌单或他人动态转发至自己的空间。
            </p>
          </motion.div>
        </section>
      </FadeIn>
    </div>
  );
};
