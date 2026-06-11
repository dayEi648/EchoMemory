import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, Clock, BarChart3, Calendar, ArrowLeft, Music, Heart } from "lucide-react";
import { toast } from "sonner";

import { usePlayerStore } from "../shared/stores/playerStore";
import { musicApi, collectionApi } from "../shared/api/instances";
import type { MusicDetail, MusicListItem } from "../shared/api/types";
import { FadeIn } from "../components/motion/FadeIn";
import { SongRow } from "../components/ui/SongRow";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { EmptyState } from "../components/ui/EmptyState";
import { CommentSection } from "../components/ui/CommentSection";

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "未知";
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const MusicDetailPage = () => {
  const { musicId } = useParams<{ musicId: string }>();
  const navigate = useNavigate();
  const playStandalone = usePlayerStore((s) => s.playStandalone);

  const [music, setMusic] = useState<MusicDetail | null>(null);
  const [related, setRelated] = useState<MusicListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [collected, setCollected] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!musicId) return;
      setLoading(true);
      try {
        const detail = await musicApi.getMusicDetail(Number(musicId));
        setMusic(detail);
        // Load related: same style or language
        const relatedList = await musicApi.listMusic({
          style_id: detail.style?.id,
          language_id: detail.language?.id,
          limit: 6,
        });
        setRelated(relatedList.items?.filter((m) => m.id !== detail.id) ?? []);
      } catch {
        toast.error("加载歌曲详情失败");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [musicId]);

  const handlePlay = () => {
    if (!music?.file_url) {
      toast.error("该歌曲暂不可播放");
      return;
    }
    playStandalone({
      id: music.id,
      title: music.title,
      is_vip: music.is_vip,
      hot: music.hot,
      play_count: music.play_count,
      cover_icon_url: music.cover_icon_url,
      authors: music.authors,
      created_at: music.created_at,
      file_url: music.file_url,
      emotion_tags: music.emotion_tags,
      interest_tags: music.interest_tags,
      albums: [],
    });
  };

  const handleToggleCollect = async () => {
    if (!music) return;
    try {
      if (collected) {
        await collectionApi.uncollectMusic(music.id);
        setCollected(false);
        toast.success("已取消收藏");
      } else {
        await collectionApi.collectMusic(music.id);
        setCollected(true);
        toast.success("已收藏");
      }
    } catch {
      toast.error("操作失败");
    }
  };

  if (loading) {
    return (
      <div className="loading-screen" style={{ height: "60vh" }}>
        <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
      </div>
    );
  }

  if (!music) {
    return <EmptyState icon={Music} title="歌曲不存在或已被删除" />;
  }

  return (
    <div>
      <FadeIn>
        <div style={{ marginBottom: 24 }}>
          <motion.button
            className="section-link"
            onClick={() => navigate(-1)}
            whileHover={{ x: -4 }}
            style={{ display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 16 }}
          >
            <ArrowLeft size={16} /> 返回
          </motion.button>

          <div
            style={{
              display: "flex",
              gap: 32,
              alignItems: "flex-start",
              flexWrap: "wrap",
            }}
          >
            {/* Cover */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              style={{
                width: 240,
                height: 240,
                borderRadius: 12,
                overflow: "hidden",
                flexShrink: 0,
                background: "var(--color-border)",
              }}
            >
              {music.cover_icon_url ? (
                <img
                  src={music.cover_icon_url}
                  alt={music.title}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "linear-gradient(135deg, #1a3a3a 0%, #2d5a5a 100%)",
                  }}
                >
                  <span style={{ fontSize: 48, fontWeight: 700, color: "rgba(255,255,255,0.3)" }}>♪</span>
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 280 }}>
              <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>{music.title}</h1>
              <div style={{ fontSize: 15, color: "var(--color-muted)", marginBottom: 16 }}>
                {music.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
              </div>

              <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
                {music.style && (
                  <span
                    style={{
                      fontSize: 12,
                      padding: "4px 10px",
                      borderRadius: 20,
                      background: "var(--color-border)",
                      fontWeight: 500,
                    }}
                  >
                    {music.style.name}
                  </span>
                )}
                {music.language && (
                  <span
                    style={{
                      fontSize: 12,
                      padding: "4px 10px",
                      borderRadius: 20,
                      background: "var(--color-border)",
                      fontWeight: 500,
                    }}
                  >
                    {music.language.name}
                  </span>
                )}
                {music.is_vip && (
                  <span
                    style={{
                      fontSize: 12,
                      padding: "4px 10px",
                      borderRadius: 20,
                      background: "var(--color-ink)",
                      color: "white",
                      fontWeight: 500,
                    }}
                  >
                    VIP
                  </span>
                )}
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 24,
                  fontSize: 13,
                  color: "var(--color-muted)",
                  marginBottom: 24,
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <BarChart3 size={14} /> {music.play_count} 次播放
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <Calendar size={14} /> {formatDate(music.release_date)}
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <Clock size={14} /> {formatDate(music.created_at)}
                </span>
              </div>

              <motion.button
                className="btn-primary"
                onClick={handlePlay}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
                style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
              >
                <Play size={18} fill="white" />
                播放
              </motion.button>
              <motion.button
                onClick={handleToggleCollect}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.92 }}
                type="button"
                title={collected ? "取消收藏" : "收藏"}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  marginLeft: 10,
                  padding: "10px 16px",
                  borderRadius: 10,
                  border: "1px solid var(--color-border)",
                  background: collected ? "var(--color-accent)" : "transparent",
                  color: collected ? "white" : "var(--color-muted)",
                  cursor: "pointer",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                <Heart size={16} fill={collected ? "white" : "none"} />
                {collected ? "已收藏" : "收藏"}
              </motion.button>
            </div>
          </div>
        </div>
      </FadeIn>

      {/* Comments */}
      {music && (
        <FadeIn delay={0.2}>
          <section style={{ marginBottom: 32 }}>
            <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>评论 ({music.comment_count})</h3>
            <CommentSection targetType="music" targetId={music.id} />
          </section>
        </FadeIn>
      )}

      {/* Related Songs */}
      {related.length > 0 && (
        <FadeIn delay={0.15}>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>相关推荐</h3>
          <StaggerContainer staggerDelay={0.04}>
            {related.map((song, i) => (
              <StaggerItem key={song.id}>
                <SongRow
                  index={i}
                  name={song.title}
                  artist={song.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
                  musicId={song.id}
                  coverUrl={song.cover_icon_url ?? undefined}
                  onPlay={async () => {
                    try {
                      const detail = await musicApi.getMusicDetail(song.id);
                      if (detail.file_url) {
                        await playStandalone({
                          id: song.id,
                          title: song.title,
                          is_vip: song.is_vip,
                          hot: song.hot,
                          play_count: song.play_count,
                          cover_icon_url: song.cover_icon_url,
                          authors: song.authors,
                          created_at: song.created_at,
                          file_url: detail.file_url,
                          emotion_tags: detail.emotion_tags,
                          interest_tags: detail.interest_tags,
                          albums: [],
                        });
                      } else {
                        toast.error("该歌曲暂不可播放");
                      }
                    } catch {
                      toast.error("加载歌曲失败");
                    }
                  }}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        </FadeIn>
      )}
    </div>
  );
};
