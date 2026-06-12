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
    cardClass: "feature-card feature-card-lavender",
    iconClass: "icon-accent-bg--lavender",
  },
  {
    icon: Heart,
    title: "情绪曲线",
    desc: "你的音乐情绪偏向平静与积极，深夜时段偶尔出现忧郁色调。",
    cardClass: "feature-card feature-card-pink",
    iconClass: "",
  },
  {
    icon: Music,
    title: "常听场景",
    desc: "工作时段占比 45%，通勤路上 30%，深夜独处 25%。",
    cardClass: "feature-card feature-card-teal",
    iconClass: "",
  },
] as const;

export const EchoPage = () => {
  return (
    <div>
      <FadeIn>
        <PageTitle icon={Sparkles} iconSize={18} iconAccent="lavender">
          AI 回声
        </PageTitle>
      </FadeIn>

      <FadeIn delay={0.08}>
        <p className="page-lead">
          EchoMemory 的 AI Agent 正在学习你的音乐品味，为你创造独特的聆听体验。
        </p>
      </FadeIn>

      <StaggerContainer staggerDelay={0.1} className="echo-cards-grid">
        {echoCards.map((card) => (
          <StaggerItem key={card.title} className="echo-card-item">
            <motion.div
              className={card.cardClass}
              whileHover={{ y: -4 }}
              transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            >
              <motion.div
                className={card.iconClass || "echo-card-icon"}
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 12,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 14,
                  background: "rgba(255,255,255,0.2)",
                }}
                whileHover={{ rotate: [0, -5, 5, 0] }}
                transition={{ duration: 0.4 }}
              >
                <card.icon size={20} />
              </motion.div>
              <h4 className="echo-card-title">{card.title}</h4>
              <p className="echo-card-desc">{card.desc}</p>
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
            accent="peach"
          />
        </section>
      </FadeIn>
    </div>
  );
};
