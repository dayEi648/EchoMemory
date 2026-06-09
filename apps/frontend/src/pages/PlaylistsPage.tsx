import { useState } from "react";
import { motion } from "framer-motion";

import { CoverCard } from "../components/ui/CoverCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";

const categories = ["全部", "流行", "摇滚", "电子", "轻音乐", "学习", "睡眠", "运动", "派对"];

const mockPlaylists = [
  { id: 1, title: "深夜回响", subtitle: "EchoMusic 编辑推荐", plays: "12.5万" },
  { id: 2, title: "Focus Flow", subtitle: "专注工作必备", plays: "8.3万" },
  { id: 3, title: "城市漫游", subtitle: "通勤路上的陪伴", plays: "6.1万" },
  { id: 4, title: "记忆碎片", subtitle: "AI 为你生成", plays: "3.2万" },
  { id: 5, title: "周末咖啡馆", subtitle: "轻音乐精选", plays: "15.7万" },
  { id: 6, title: "电子脉冲", subtitle: "电子音乐精选", plays: "9.8万" },
  { id: 7, title: "雨天窗前", subtitle: "舒缓心情", plays: "4.5万" },
  { id: 8, title: "公路旅行", subtitle: "驾驶必备", plays: "7.2万" },
];

export const PlaylistsPage = () => {
  const [activeCat, setActiveCat] = useState("全部");

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">播放列表广场</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          {categories.map((cat) => (
            <motion.button
              key={cat}
              className={`tag-pill ${cat === activeCat ? "active" : ""}`}
              onClick={() => setActiveCat(cat)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              type="button"
            >
              {cat}
            </motion.button>
          ))}
        </div>
      </FadeIn>

      <section style={{ marginBottom: 32 }}>
        <SectionHeader title="精选歌单" />
        <StaggerContainer className="playlist-rail">
          {mockPlaylists.map((p) => (
            <StaggerItem key={p.id}>
              <CoverCard
                id={p.id}
                title={p.title}
                subtitle={`${p.subtitle} · ${p.plays}次播放`}
              />
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>
    </div>
  );
};
