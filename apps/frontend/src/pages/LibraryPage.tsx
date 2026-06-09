import { Heart, Music2, UserCheck } from "lucide-react";
import { useState } from "react";
import { motion } from "framer-motion";

import { EmptyState } from "../components/ui/EmptyState";
import { FadeIn } from "../components/motion/FadeIn";

const tabs = [
  { key: "songs", label: "收藏歌曲", icon: Heart },
  { key: "playlists", label: "收藏歌单", icon: Music2 },
  { key: "following", label: "关注用户", icon: UserCheck },
];

export const LibraryPage = () => {
  const [activeTab, setActiveTab] = useState("songs");

  const emptyMessages: Record<string, { title: string; desc: string }> = {
    songs: { title: "暂无收藏歌曲", desc: "在浏览歌单或歌曲时点击收藏，它们将出现在这里。" },
    playlists: { title: "暂无收藏歌单", desc: "发现喜欢的歌单后点击收藏，随时重温。" },
    following: { title: "暂无关注", desc: "关注你喜欢的音乐人或其他用户，不错过他们的动态。" },
  };

  const current = emptyMessages[activeTab];
  const CurrentIcon = tabs.find((t) => t.key === activeTab)?.icon ?? Heart;

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">我的收藏</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div className="search-tabs">
          {tabs.map((tab) => (
            <motion.button
              key={tab.key}
              className={`search-tab ${activeTab === tab.key ? "active" : ""}`}
              onClick={() => setActiveTab(tab.key)}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              <tab.icon size={14} />
              {tab.label}
            </motion.button>
          ))}
        </div>
      </FadeIn>

      <FadeIn delay={0.15}>
        <EmptyState icon={CurrentIcon} title={current.title} description={current.desc} />
      </FadeIn>
    </div>
  );
};
