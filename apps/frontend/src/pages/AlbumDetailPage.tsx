import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, BarChart3, ArrowLeft, Music, Disc3, Heart } from "lucide-react";
import { toast } from "sonner";

import { usePlayerStore } from "../shared/stores/playerStore";
import { createAlbumApi } from "../shared/api/albumApi";
import { createMusicApi } from "../shared/api/musicApi";
import { createCollectionApi } from "../shared/api/collectionApi";
import { createLocalStorageTokenStore } from "../shared/auth/tokenStore";
import type { AlbumDetail } from "../shared/api/types";
import { FadeIn } from "../components/motion/FadeIn";
import { SongRow } from "../components/ui/SongRow";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { EmptyState } from "../components/ui/EmptyState";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const albumApi = createAlbumApi({ baseUrl: API_BASE_URL, tokenStore });
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });
const collectionApi = createCollectionApi({ baseUrl: API_BASE_URL, tokenStore });

export const AlbumDetailPage = () => {
  const { albumId } = useParams<{ albumId: string }>();
  const navigate = useNavigate();
  const playTrack = usePlayerStore((s) => s.playTrack);
  const playInContext = usePlayerStore((s) => s.playInContext);
  const playQueue = usePlayerStore((s) => s.playQueue);

  const [album, setAlbum] = useState<AlbumDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [collected, setCollected] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!albumId) return;
      setLoading(true);
      try {
        const detail = await albumApi.getAlbumDetail(Number(albumId));
        // 获取每首歌曲的 file_url 以支持播放
        const musicsWithUrl = await Promise.all(
          detail.musics.map(async (m) => {
            try {
              const musicDetail = await musicApi.getMusicDetail(m.id);
              return { ...m, file_url: musicDetail.file_url };
            } catch {
              return m;
            }
          }),
        );
        setAlbum({ ...detail, musics: musicsWithUrl });
      } catch {
        toast.error("加载专辑详情失败");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [albumId]);

  const handleToggleCollect = async () => {
    if (!album) return;
    try {
      if (collected) {
        await collectionApi.uncollectAlbum(album.id);
        setCollected(false);
        toast.success("已取消收藏");
      } else {
        await collectionApi.collectAlbum(album.id);
        setCollected(true);
        toast.success("已收藏");
      }
    } catch {
      toast.error("操作失败");
    }
  };

  const handlePlayAll = () => {
    if (!album || album.musics.length === 0) return;
    const tracks = album.musics
      .filter((m): m is typeof m & { file_url: string } => !!m.file_url)
      .map((m) => ({
        id: m.id,
        title: m.title,
        is_vip: m.is_vip,
        hot: m.hot,
        play_count: m.play_count,
        cover_icon_url: m.cover_icon_url,
        authors: album.authors,
        created_at: album.created_at,
        file_url: m.file_url ?? null,
        emotion_tags: [],
        interest_tags: [],
        albums: [],
      }));
    if (tracks.length > 0) {
      playQueue(tracks, 0);
    } else {
      toast.error("暂无可播放的歌曲");
    }
  };

  const handlePlayMusic = (music: AlbumDetail["musics"][0]) => {
    if (!music.file_url) {
      toast.error("该歌曲暂不可播放");
      return;
    }
    if (!album) return;

    // 以整个专辑为上下文构建队列
    const contextTracks = album.musics.map((m) => ({
      id: m.id,
      title: m.title,
      is_vip: m.is_vip,
      hot: m.hot,
      play_count: m.play_count,
      cover_icon_url: m.cover_icon_url,
      authors: album.authors,
      emotion_tags: [],
      interest_tags: [],
      albums: [],
      created_at: album.created_at,
      file_url: m.file_url ?? null,
    }));

    playInContext(
      contextTracks.find((t) => t.id === music.id)!,
      contextTracks,
      { type: "album", id: album.id, name: album.title },
    );
  };

  if (loading) {
    return (
      <div className="loading-screen" style={{ height: "60vh" }}>
        <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
      </div>
    );
  }

  if (!album) {
    return <EmptyState icon={Disc3} title="专辑不存在或已被删除" />;
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
              {album.cover_icon_url ? (
                <img
                  src={album.cover_icon_url}
                  alt={album.title}
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
                  <Music size={48} color="rgba(255,255,255,0.3)" />
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 280 }}>
              <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>{album.title}</h1>
              {album.description && (
                <p style={{ fontSize: 14, color: "var(--color-muted)", marginBottom: 16, lineHeight: 1.6 }}>
                  {album.description}
                </p>
              )}

              <div style={{ fontSize: 15, color: "var(--color-muted)", marginBottom: 16 }}>
                {album.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
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
                  <BarChart3 size={14} /> {album.play_count} 次播放
                </span>
                <span>{album.musics.length} 首歌曲</span>
              </div>

              <motion.button
                className="btn-primary"
                onClick={handlePlayAll}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
                style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
              >
                <Play size={18} fill="white" />
                播放全部
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

      {/* Songs */}
      <FadeIn delay={0.15}>
        <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>歌曲列表</h3>
        {album.musics.length === 0 ? (
          <EmptyState icon={Music} title="该专辑暂无歌曲" />
        ) : (
          <StaggerContainer staggerDelay={0.04}>
            {album.musics.map((music, i) => (
              <StaggerItem key={music.id}>
                <SongRow
                  index={i}
                  name={music.title}
                  artist={album.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
                  musicId={music.id}
                  coverUrl={music.cover_icon_url ?? undefined}
                  onPlay={() => handlePlayMusic(music)}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        )}
      </FadeIn>
    </div>
  );
};
