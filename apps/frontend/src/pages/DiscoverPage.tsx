import { Play, Sparkles, TrendingUp, Clock, Disc, Music } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { useAuthStore } from "../shared/stores/authStore";
import { usePlayerStore } from "../shared/stores/playerStore";
import { musicApi } from "../shared/api/instances";
import { albumApi } from "../shared/api/instances";
import { playHistoryApi } from "../shared/api/instances";
import type { MusicListItem, AlbumListItem, PlayHistoryItem } from "../shared/api/types";
import { calcLevelProgress, formatAlbumTitle, formatAuthors, toPlayerTrackFromListItem } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { CoverCard } from "../components/ui/CoverCard";
import { SongRow } from "../components/ui/SongRow";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";

export const DiscoverPage = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const playQueue = usePlayerStore((s) => s.playQueue);
  const { playMusicListItem, playMusicById } = usePlayMusic();

  const [newSongs, setNewSongs] = useState<MusicListItem[]>([]);
  const [albums, setAlbums] = useState<AlbumListItem[]>([]);
  const [recentPlays, setRecentPlays] = useState<PlayHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [songs, albumList, history] = await Promise.all([
          musicApi.listMusic({ limit: 8 }),
          albumApi.listAlbums({ limit: 5 }),
          playHistoryApi.listPlayHistory({ limit: 5 }),
        ]);
        setNewSongs(songs.items ?? []);
        setAlbums(albumList.items ?? []);
        setRecentPlays(history.items ?? []);
      } catch {
        toast.error("加载内容失败，请稍后重试");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handlePlayRecommend = async () => {
    if (newSongs.length === 0) return;
    const tracks = [];
    for (const song of newSongs.slice(0, 5)) {
      try {
        const detail = await musicApi.getMusicDetail(song.id);
        if (detail.file_url) {
          tracks.push(toPlayerTrackFromListItem(song, detail.file_url));
        }
      } catch {
        // skip
      }
    }
    if (tracks.length > 0) {
      playQueue(tracks, 0, { type: "temporary" });
    } else {
      toast.error("暂无可播放的歌曲");
    }
  };

  if (loading) {
    return (
      <div className="loading-screen" style={{ height: "60vh" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: "var(--color-ink)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              animation: "pulse-loading 1.5s ease-in-out infinite",
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <div style={{ fontSize: 14, fontWeight: 500 }}>正在加载音乐...</div>
        </div>
      </div>
    );
  }

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
                onClick={handlePlayRecommend}
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
                {recentPlays.length === 0 ? (
                  <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0, lineHeight: 1.6 }}>
                    暂无最近播放记录。开始听歌后，这里会显示你最近聆听的歌曲。
                  </p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {recentPlays.map((item) => (
                      <div
                        key={item.id}
                        className="hero-recent-item"
                        onClick={() => playMusicById(item.music.id)}
                      >
                        <img
                          src={item.music.cover_icon_url ?? undefined}
                          alt={item.music.title}
                        />
                        <div style={{ minWidth: 0 }}>
                          <div className="hero-recent-title">{item.music.title}</div>
                          <div className="hero-recent-artist">未知艺人</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </FadeIn>
            {user && (
              <FadeIn delay={0.25}>
                <div className="hero-sidebar-card">
                  <h4><TrendingUp size={12} /> 等级进度</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 24, fontWeight: 700, color: "var(--color-brand-coral)" }}>
                      Lv.{user.level}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div className="level-progress-bar">
                        <motion.div
                          className="level-progress-fill"
                          initial={{ width: 0 }}
                          animate={{ width: `${calcLevelProgress(user.exp, user.level)}%` }}
                          transition={{ duration: 0.8, delay: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
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

      {/* Recommended Albums */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader
          title="为你推荐的专辑"
          action={
            <button className="section-link" onClick={() => navigate("/search?tab=albums")} type="button">
              查看全部 →
            </button>
          }
        />
        <StaggerContainer className="playlist-rail">
          {albums.map((album) => (
            <StaggerItem key={album.id}>
              <CoverCard
                id={album.id}
                title={album.title}
                subtitle={`播放量 ${album.play_count}`}
                coverUrl={album.cover_icon_url ?? undefined}
                onClick={() => navigate(`/album/${album.id}`)}
              />
            </StaggerItem>
          ))}
          {albums.length === 0 && <EmptyState icon={Disc} title="暂无推荐专辑" accent="lavender" />}
        </StaggerContainer>
      </section>

      {/* New Songs */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader title="新歌上架" />
        <StaggerContainer staggerDelay={0.04}>
          {newSongs.map((song, i) => (
            <StaggerItem key={song.id}>
              <SongRow
                name={song.title}
                artist={formatAuthors(song.authors)}
                album={formatAlbumTitle(song.albums)}
                playCount={song.play_count}
                musicId={song.id}
                coverUrl={song.cover_icon_url ?? undefined}
                onPlay={() => playMusicListItem(song)}
              />
            </StaggerItem>
          ))}
          {newSongs.length === 0 && <EmptyState icon={Music} title="暂无新歌上架" accent="peach" />}
        </StaggerContainer>
      </section>

      {/* Hot new songs */}
      <section style={{ marginBottom: 32 }}>
        <SectionHeader
          title={
            <>
              <TrendingUp size={16} style={{ display: "inline", verticalAlign: "-2px" }} /> 热门新歌
            </>
          }
        />
        <StaggerContainer staggerDelay={0.04}>
          {newSongs.slice(0, 5).map((song, i) => (
            <StaggerItem key={song.id}>
              <SongRow
                index={i}
                showIndex
                name={song.title}
                artist={formatAuthors(song.authors)}
                album={formatAlbumTitle(song.albums)}
                playCount={song.play_count}
                musicId={song.id}
                coverUrl={song.cover_icon_url ?? undefined}
                onPlay={() => playMusicListItem(song)}
              />
            </StaggerItem>
          ))}
          {newSongs.length === 0 && <EmptyState icon={TrendingUp} title="暂无排行数据" accent="ochre" />}
        </StaggerContainer>
      </section>
    </div>
  );
};
