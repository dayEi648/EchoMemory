import { Activity, Users, Music, Shield } from "lucide-react";
import { motion } from "framer-motion";

import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";

const statCards = [
  { label: "注册用户", value: "1,248", icon: Users, cardClass: "dashboard-stat-card dashboard-stat-card--lavender" },
  { label: "音乐数量", value: "3,672", icon: Music, cardClass: "dashboard-stat-card dashboard-stat-card--teal" },
  { label: "待审核内容", value: "12", icon: Shield, cardClass: "dashboard-stat-card dashboard-stat-card--pink" },
  { label: "今日活跃", value: "156", icon: Activity, cardClass: "dashboard-stat-card dashboard-stat-card--ochre" },
] as const;

export const AdminDashboardPage = () => (
  <div>
    <FadeIn>
      <h1 className="page-title">管理概览</h1>
      <p className="panel-muted-text" style={{ marginTop: 8, marginBottom: 0 }}>
        以下统计数据为示例数据，待后端统计接口上线后将展示真实数值。
      </p>
    </FadeIn>

    <StaggerContainer staggerDelay={0.08} className="admin-stats-grid">
      {statCards.map((card) => (
        <StaggerItem key={card.label}>
          <motion.div
            className={card.cardClass}
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
            <div className="stat-value">{card.value}</div>
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
            系统运行正常。所有服务均在线。管理后台各模块功能即将陆续上线。
          </p>
        </motion.div>
      </section>
    </FadeIn>
  </div>
);
