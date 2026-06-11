import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, ListMusic, ArrowLeft, Music, Lock, Heart } from "lucide-react";
import { toast } from "sonner";

import { usePlayerStore } from "../shared/stores/playerStore";
import { useAuthStore } from "../shared/stores/authStore";
import { createPlaylistApi } from "../shared/api/playlistApi";
import { createMusicApi } from "../shared/api/musicApi";
import { createCollectionApi } from "../shared/api/collectionApi";
import { createLocalStorageTokenStore } from "../shared/auth/tokenStore";
import type { PlaylistDetail as PlaylistDetailType, MusicListItem } from "../shared/api/types";
import { formatAuthors } from "../shared/utils";
import { Avatar } from "../components/ui/Avatar";
import { SongRow } from "../components/ui/SongRow";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { CommentSection } from "../components/ui/CommentSection";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const playlistApi = createPlaylistApi({ baseUrl: API_BASE_URL, tokenStore });
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });
const collectionApi = createCollectionApi({ baseUrl: API_BASE_URL, tokenStore });

export const PlaylistDetailPage = () => {
  const { playlistId } = useParams<{ playlistId: string }>();
  const navigate = useNavigate();
  const playInContext = usePlayerStore((s) => s.playInContext);
  const { user: currentUser } = useAuthStore();

  const [playlist, setPlaylist] = useState<PlaylistDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [collected, setCollected] = useState(false);

  useEffect(() => {
    const load = async () => {
      if (!playlistId) return;
      setLoading(true);
      try {
        const detail = await playlistApi.getPlaylistDetail(Number(playlistId));
        setPlaylist(detail);
      } catch {
        toast.error("加载歌单详情失败");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [playlistId]);

  const handleToggleCollect = async () => {
    if (!playlist) return;
    try {
      if (collected) {
        await collectionApi.uncollectPlaylist(playlist.id);
        setCollected(false);
        toast.success("已取消收藏");
      } else {
        await collectionApi.collectPlaylist(playlist.id);
        setCollected(true);
        toast.success("已收藏");
      }
    } catch {
      toast.error("操作失败");
    }
  };

  /** 播放全部：获取每首歌的 file_url 后以歌单为上下文播放 */
  const handlePlayAll = async () => {
    if (!playlist || playlist.musics.length === 0) return;
    const sortedMusics = [...playlist.musics].sort((a, b) => a.ordinal - b.ordinal);

    const tracks = await Promise.all(
      sortedMusics.map(async (pm) => {
        try {
          const detail = await musicApi.getMusicDetail(pm.music.id);
          return {
            id: pm.music.id,
            title: pm.music.title,
            is_vip: pm.music.is_vip,
            hot: pm.music.hot,
            play_count: pm.music.play_count,
            cover_icon_url: pm.music.cover_icon_url,
            authors: pm.music.authors,
            emotion_tags: [],
            interest_tags: [],
            albums: [],
            created_at: pm.music.created_at,
            file_url: detail.file_url,
          };
        } catch {
          return null;
        }
      }),
    );

    const validTracks = tracks.filter((t): t is NonNullable<typeof t> => t !== null && !!t.file_url);
    if (validTracks.length > 0) {
      playInContext(validTracks[0], validTracks, {
        type: "playlist",
        id: playlist.id,
        name: playlist.title,
      });
    } else {
      toast.error("暂无可播放的歌曲");
    }
  };

  /** 点击单曲：以整个歌单为上下文播放 */
  const handlePlayMusic = async (pm: PlaylistDetailType["musics"][0]) => {
    const sortedMusics = [...(playlist?.musics ?? [])].sort((a, b) => a.ordinal - b.ordinal);

    // 先加载点击歌曲的 file_url
    let currentTrack;
    let detail: Awaited<ReturnType<typeof musicApi.getMusicDetail>>;
    try {
      detail = await musicApi.getMusicDetail(pm.music.id);
      if (!detail.file_url) {
        toast.error("该歌曲暂不可播放");
        return;
      }
      currentTrack = {
        id: pm.music.id,
        title: pm.music.title,
        is_vip: pm.music.is_vip,
        hot: pm.music.hot,
        play_count: pm.music.play_count,
        cover_icon_url: pm.music.cover_icon_url,
        authors: pm.music.authors,
        emotion_tags: [],
        interest_tags: [],
        albums: [],
        created_at: pm.music.created_at,
        file_url: detail.file_url,
      };
    } catch {
      toast.error("加载歌曲失败");
      return;
    }

    // 构建上下文队列（其他歌曲 lazily loaded）
    const contextTracks = sortedMusics.map((m): MusicListItem & { file_url: string | null } => ({
      id: m.music.id,
      title: m.music.title,
      is_vip: m.music.is_vip,
      hot: m.music.hot,
      play_count: m.music.play_count,
      cover_icon_url: m.music.cover_icon_url,
      authors: m.music.authors,
      emotion_tags: [],
      interest_tags: [],
      albums: [],
      created_at: m.music.created_at,
      file_url: m.music.id === pm.music.id ? detail.file_url : null,
    }));

    playInContext(currentTrack, contextTracks, {
      type: "playlist",
      id: playlist!.id,
      name: playlist!.title,
    });
  };

  if (loading) {
    return (
      <div className="loading-screen" style={{ height: "60vh" }}>
        <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
      </div>
    );
  }

  if (!playlist) {
    return <EmptyState icon={ListMusic} title="歌单不存在或已被删除" />;
  }

  const sortedMusics = [...playlist.musics].sort((a, b) => a.ordinal - b.ordinal);
  const isOwner = currentUser?.id === playlist.user.id;

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
              {playlist.cover_icon_url ? (
                <img
                  src={playlist.cover_icon_url}
                  alt={playlist.title}
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
                  <ListMusic size={48} color="rgba(255,255,255,0.3)" />
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 280 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>{playlist.title}</h1>
                {playlist.is_private && (
                  <span title="私密歌单" style={{ color: "var(--color-muted)" }}>
                    <Lock size={16} />
                  </span>
                )}
              </div>

              {playlist.description && (
                <p style={{ fontSize: 14, color: "var(--color-muted)", marginBottom: 16, lineHeight: 1.6 }}>
                  {playlist.description}
                </p>
              )}

              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <Avatar user={playlist.user} size="sm" />
                <span style={{ fontSize: 14, fontWeight: 500 }}>{playlist.user.nickname}</span>
                <span style={{ fontSize: 13, color: "var(--color-muted)" }}>@{playlist.user.username}</span>
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
                <span>{playlist.musics.length} 首歌曲</span>
                <span>{playlist.play_count} 次播放</span>
                <span>{playlist.collect_count} 次收藏</span>
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

              {!isOwner && (
                <span style={{ fontSize: 12, color: "var(--color-muted)", marginLeft: 12 }}>
                  仅歌单创建者可编辑
                </span>
              )}
            </div>
          </div>
        </div>
      </FadeIn>

      {/* Comments */}
      {playlist && (
        <FadeIn delay={0.2}>
          <section style={{ marginBottom: 32 }}>
            <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>评论 ({playlist.comment_count})</h3>
            <CommentSection targetType="playlist" targetId={playlist.id} />
          </section>
        </FadeIn>
      )}

      {/* Songs */}
      <FadeIn delay={0.15}>
        <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>歌曲列表</h3>
        {sortedMusics.length === 0 ? (
          <EmptyState icon={Music} title="该歌单暂无歌曲" description="歌单创建者可以通过搜索将歌曲添加到歌单。" />
        ) : (
          <StaggerContainer staggerDelay={0.04}>
            {sortedMusics.map((pm, i) => (
              <StaggerItem key={`${pm.music.id}-${pm.ordinal}`}>
                <SongRow
                  index={i}
                  name={pm.music.title}
                  artist={formatAuthors(pm.music.authors)}
                  musicId={pm.music.id}
                  coverUrl={pm.music.cover_icon_url ?? undefined}
                  onPlay={() => handlePlayMusic(pm)}
                />
              </StaggerItem>
            ))}
          </StaggerContainer>
        )}
      </FadeIn>
    </div>
  );
};
