import { Sparkles, Music, Brain, Heart } from "lucide-react";
import { motion } from "framer-motion";

import { EmptyState } from "../components/ui/EmptyState";
import { PageTitle } from "../components/ui/PageTitle";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";

const echoCards = [
  {
    icon: Brain,
    title: "偏好风格",
    desc: "根据你的听歌历史，AI 发现你偏爱独立流行和电子音乐。",
    color: "#8d7cf6",
  },
  {
    icon: Heart,
    title: "情绪曲线",
    desc: "你的音乐情绪偏向平静与积极，深夜时段偶尔出现忧郁色调。",
    color: "#ff5b57",
  },
  {
    icon: Music,
    title: "常听场景",
    desc: "工作时段占比 45%，通勤路上 30%，深夜独处 25%。",
    color: "#2bb3a3",
  },
];

export const EchoPage = () => {
  return (
    <div>
      <FadeIn>
        <PageTitle icon={Sparkles} iconSize={22}>AI 回声</PageTitle>
      </FadeIn>

      <FadeIn delay={0.08}>
        <p style={{ color: "var(--color-muted)", fontSize: 14, marginBottom: 24 }}>
          EchoMemory 的 AI Agent 正在学习你的音乐品味，为你创造独特的聆听体验。
        </p>
      </FadeIn>

      <StaggerContainer
        staggerDelay={0.1}
        className="echo-cards-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 16,
          marginBottom: 32,
        }}
      >
        {echoCards.map((card) => (
          <StaggerItem key={card.title}>
            <motion.div
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
                borderRadius: 14,
                padding: 22,
                height: "100%",
              }}
              whileHover={{
                y: -3,
                boxShadow: "0 8px 24px rgba(0,0,0,0.06)",
              }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <motion.div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: `${card.color}15`,
                  color: card.color,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 14,
                }}
                whileHover={{ rotate: [0, -5, 5, 0] }}
                transition={{ duration: 0.4 }}
              >
                <card.icon size={20} />
              </motion.div>
              <h4 style={{ fontSize: 15, fontWeight: 700, margin: "0 0 8px" }}>{card.title}</h4>
              <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0, lineHeight: 1.6 }}>
                {card.desc}
              </p>
            </motion.div>
          </StaggerItem>
        ))}
      </StaggerContainer>

      <FadeIn delay={0.35}>
        <section>
          <div className="section-header">
            <h3>AI 推荐歌单</h3>
          </div>
          <EmptyState
            icon={Sparkles}
            title="更多推荐即将到来"
            description="AI 正在分析你的听歌数据，为你准备专属推荐歌单和记忆片段。"
          />
        </section>
      </FadeIn>
    </div>
  );
};
