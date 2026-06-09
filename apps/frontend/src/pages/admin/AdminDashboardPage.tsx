import { Activity, Users, Music, Shield } from "lucide-react";
import { motion } from "framer-motion";

import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";

const statCards = [
  { label: "注册用户", value: "1,248", icon: Users, color: "#8d7cf6" },
  { label: "音乐数量", value: "3,672", icon: Music, color: "#2bb3a3" },
  { label: "待审核内容", value: "12", icon: Shield, color: "#ff5b57" },
  { label: "今日活跃", value: "156", icon: Activity, color: "#b8860b" },
];

export const AdminDashboardPage = () => (
  <div>
    <FadeIn>
      <h1 className="page-title">管理概览</h1>
    </FadeIn>

    <StaggerContainer
      staggerDelay={0.08}
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
        gap: 16,
        marginBottom: 28,
      }}
    >
      {statCards.map((card) => (
        <StaggerItem key={card.label}>
          <motion.div
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              padding: 20,
            }}
            whileHover={{
              y: -3,
              boxShadow: "0 6px 20px rgba(0,0,0,0.06)",
            }}
            transition={{ duration: 0.25 }}
          >
            <motion.div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: `${card.color}15`,
                color: card.color,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 12,
              }}
              whileHover={{ rotate: [0, -5, 5, 0] }}
              transition={{ duration: 0.4 }}
            >
              <card.icon size={18} />
            </motion.div>
            <div style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>{card.value}</div>
            <div style={{ fontSize: 12, color: "var(--color-muted)", fontWeight: 500 }}>{card.label}</div>
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
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: 12,
            padding: 20,
          }}
          whileHover={{ boxShadow: "0 4px 12px rgba(0,0,0,0.04)" }}
          transition={{ duration: 0.25 }}
        >
          <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0 }}>
            系统运行正常。所有服务均在线。管理后台各模块功能即将陆续上线。
          </p>
        </motion.div>
      </section>
    </FadeIn>
  </div>
);