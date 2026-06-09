import { Play, Sparkles, TrendingUp, Clock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

import { useAuthStore } from "../shared/stores/authStore";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";

const mockPlaylists = [
  { id: 1, title: "深夜回响", subtitle: "EchoMusic 编辑推荐" },
  { id: 2, title: "Focus Flow", subtitle: "专注工作必备" },
  { id: 3, title: "城市漫游", subtitle: "通勤路上的陪伴" },
  { id: 4, title: "记忆碎片", subtitle: "AI 为你生成" },
  { id: 5, title: "周末咖啡馆", subtitle: "轻音乐精选" },
];

const mockNewSongs = [
  { id: 1, name: "夏日尾声", artist: "回声乐团", album: "季节系列" },
  { id: 2, name: "量子梦境", artist: "AI Composer", album: "未来之声" },
  { id: 3, name: "山涧流水", artist: "自然录音室", album: "自然音景" },
  { id: 4, name: "都市霓虹", artist: "CityBeats", album: "夜行" },
  { id: 5, name: "古典回响", artist: "弦乐四重奏", album: "经典重现" },
];

const mockChart = [
  { rank: 1, name: "回声记忆", artist: "EchoMemory" },
  { rank: 2, name: "时光隧道", artist: "TimeTravel" },
  { rank: 3, name: "星海漫步", artist: "StarWalker" },
  { rank: 4, name: "雨后初晴", artist: "RainDrop" },
  { rank: 5, name: "暮色温柔", artist: "Twilight" },
];

export const DiscoverPage = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  return (
    <div>
      {/* Hero Section */}
      <FadeIn>
        <div className="hero-section">
          <motion.div
            className="hero-banner"
            whileHover={{ scale: 1.005 }}
            transition={{ duration: 0.4 }}
          >
            {/* animated background orbs */}
            <div style={{ position: "absolute", inset: 0, overflow: "hidden", borderRadius: 16 }}>
              <motion.div
                animate={{ x: [0, 20, 0], y: [0, -15, 0] }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  position: "absolute",
                  width: 200,
                  height: 200,
                  borderRadius: "50%",
                  background: "rgba(255,255,255,0.06)",
                  top: "10%",
                  left: "60%",
                }}
              />
              <motion.div
                animate={{ x: [0, -15, 0], y: [0, 20, 0] }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
                style={{
                  position: "absolute",
                  width: 160,
                  height: 160,
                  borderRadius: "50%",
                  background: "rgba(255,255,255,0.04)",
                  bottom: "15%",
                  left: "15%",
                }}
              />
            </div>

            <div className="hero-tag">
              <Sparkles size={14} />
              今日推荐
            </div>
            <h2>{user ? `欢迎回来，${user.nickname}` : "发现你的音乐记忆"}</h2>
            <p>
              {user
                ? "你的音乐偏好会随着听歌历史逐步形成更清晰的回声画像。让 AI 为你推荐下一首心动。"
                : "EchoMemory 用 AI Agent 理解你的音乐品味，创造独特的聆听体验。"}
            </p>
            <div className="hero-cta">
              <motion.button
                className="btn-primary"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
              >
                <Play size={16} fill="white" />
                播放今日推荐
              </motion.button>
              <motion.button
                className="btn-secondary"
                onClick={() => navigate("/echo")}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
              >
                <Sparkles size={16} />
                查看 AI 回声
              </motion.button>
            </div>
          </motion.div>

          <div className="hero-sidebar">
            <FadeIn delay={0.15}>
              <div className="hero-sidebar-card">
                <h4><Clock size={12} /> 最近播放</h4>
                <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0, lineHeight: 1.6 }}>
                  暂无最近播放记录。开始听歌后，这里会显示你最近聆听的歌曲。
                </p>
              </div>
            </FadeIn>
            {user && (
              <FadeIn delay={0.25}>
                <div className="hero-sidebar-card">
                  <h4><TrendingUp size={12} /> 等级进度</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 24, fontWeight: 700, color: "var(--color-accent)" }}>
                      Lv.{user.level}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          height: 6,
                          background: "var(--color-border)",
                          borderRadius: 3,
                          overflow: "hidden",
                        }}
                      >
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: "35%" }}
                          transition={{ duration: 0.8, delay: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
                          style={{
                            height: "100%",
                            background: "var(--color-accent)",
                            borderRadius: 3,
                          }}
                        />
                      </div>
                      <span style={{ fontSize: 11, color: "var(--color-muted)" }}>{user.exp} EXP</span>
                    </div>
                  </div>
                </div>
              </FadeIn>
            )}
          </div>
        </div>
      </FadeIn>

      {/* Recommended Playlists */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader
          title="为你推荐的歌单"
          action={
            <button className="section-link" onClick={() => navigate("/playlists")} type="button">
              查看全部 →
            </button>
          }
        />
        <StaggerContainer className="playlist-rail">
          {mockPlaylists.map((p) => (
            <StaggerItem key={p.id}>
              <CoverCard id={p.id} title={p.title} subtitle={p.subtitle} />
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>

      {/* New Songs */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader title="新歌上架" />
        <StaggerContainer staggerDelay={0.04}>
          {mockNewSongs.map((song, i) => (
            <StaggerItem key={song.id}>
              <SongRow
                index={i}
                name={song.name}
                artist={song.artist}
                album={song.album}
                duration="3:42"
              />
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>

      {/* Chart */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader
          title={
            <>
              <TrendingUp size={16} style={{ display: "inline", verticalAlign: "-2px" }} /> 排行榜
            </>
          }
        />
        <StaggerContainer staggerDelay={0.04}>
          {mockChart.map((item, i) => (
            <StaggerItem key={item.rank}>
              <SongRow
                index={i}
                name={item.name}
                artist={item.artist}
                album="热歌榜"
                showHeart
              />
            </StaggerItem>
          ))}
        </StaggerContainer>
      </section>
    </div>
  );
};
