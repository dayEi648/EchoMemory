import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, ListMusic, ArrowLeft, Music, Lock, Heart, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { usePlayerStore } from "../shared/stores/playerStore";
import { useAuthStore } from "../shared/stores/authStore";
import { playlistApi, musicApi, collectionApi } from "../shared/api/instances";
import type { PlaylistDetail as PlaylistDetailType, PlaylistListItem } from "../shared/api/types";
import { formatAlbumTitle, formatAuthors, toPlayerTrackFromListItem } from "../shared/utils";
import { Avatar } from "../components/ui/Avatar";
import { SongRow } from "../components/ui/SongRow";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { CommentSection } from "../components/ui/CommentSection";
import { CreatePlaylistModal } from "../components/ui/CreatePlaylistModal";
import { ConfirmDeleteModal } from "../components/ui/ConfirmDeleteModal";
import { getApiErrorMessage } from "../shared/apiError";
import { ErrorCode } from "../shared/constants/errorCode";
import { ApiError } from "../shared/api/base";

type PlaylistTab = "songs" | "comments";

export const PlaylistDetailPage = () => {
  const { playlistId } = useParams<{ playlistId: string }>();
  const navigate = useNavigate();
  const playInContext = usePlayerStore((s) => s.playInContext);
  const { user: currentUser } = useAuthStore();

  const [playlist, setPlaylist] = useState<PlaylistDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [collected, setCollected] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [tab, setTab] = useState<PlaylistTab>("songs");

  useEffect(() => {
    const load = async () => {
      if (!playlistId) return;
      setLoading(true);
      try {
        const detail = await playlistApi.getPlaylistDetail(Number(playlistId));
        setPlaylist(detail);
        setCollected(detail.is_collected_by_me ?? false);
      } catch (err) {
        toast.error(getApiErrorMessage(err, "加载歌单详情失败"));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [playlistId]);

  useEffect(() => {
    setTab("songs");
  }, [playlistId]);

  const handleToggleCollect = async () => {
    if (!playlist || currentUser?.id === playlist.user.id) return;
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
    } catch (err) {
      if (err instanceof ApiError && err.is(ErrorCode.CANNOT_COLLECT_OWN_PLAYLIST)) {
        toast.error("不能收藏自己的歌单");
      } else {
        toast.error(getApiErrorMessage(err, "操作失败"));
      }
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
          return toPlayerTrackFromListItem(pm.music, detail.file_url);
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
      currentTrack = toPlayerTrackFromListItem(pm.music, detail.file_url);
    } catch {
      toast.error("加载歌曲失败");
      return;
    }

    // 构建上下文队列（其他歌曲 lazily loaded）
    const contextTracks = sortedMusics.map((m) =>
      toPlayerTrackFromListItem(
        m.music,
        m.music.id === pm.music.id ? detail.file_url : null,
      ),
    );

    playInContext(currentTrack, contextTracks, {
      type: "playlist",
      id: playlist!.id,
      name: playlist!.title,
    });
  };

  const handleUpdated = (updated: PlaylistListItem) => {
    if (playlist) {
      setPlaylist({
        ...playlist,
        title: updated.title,
        is_private: updated.is_private,
        cover_icon_url: updated.cover_icon_url,
      });
    }
  };

  const handleDeleteConfirm = async () => {
    if (!playlist) return;
    setDeleting(true);
    try {
      await playlistApi.deletePlaylist(playlist.id);
      toast.success("歌单已删除");
      setDeleteModalOpen(false);
      navigate("/playlists", { replace: true });
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除失败"));
    } finally {
      setDeleting(false);
    }
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
  /** 歌单收藏：仅对他人公开歌单可用（决策 §8） */
  const canCollectPlaylist = !isOwner && !playlist.is_private;

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

          <div className="detail-header">
            {/* Cover */}
            <motion.div
              className="detail-cover"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
            >
              {playlist.cover_icon_url ? (
                <img
                  src={playlist.cover_icon_url}
                  alt={playlist.title}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              ) : (
                <div className="detail-cover-placeholder">
                  <ListMusic size={48} color="rgba(255,255,255,0.3)" />
                </div>
              )}
            </motion.div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 280 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <h1 className="detail-title" style={{ margin: 0 }}>{playlist.title}</h1>
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

              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
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

                {canCollectPlaylist && (
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
                )}

                {/* 所有者操作按钮 */}
                {isOwner && (
                  <>
                    <motion.button
                      className="btn-secondary"
                      onClick={() => setEditModalOpen(true)}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      type="button"
                      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                    >
                      <Pencil size={14} />
                      编辑
                    </motion.button>
                    <motion.button
                      className="btn-secondary"
                      onClick={() => setDeleteModalOpen(true)}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      type="button"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 6,
                        color: "var(--color-error)",
                        borderColor: "var(--color-error)",
                      }}
                    >
                      <Trash2 size={14} />
                      删除
                    </motion.button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>
      </FadeIn>

      {/* 歌曲列表 / 评论 切换 */}
      <FadeIn delay={0.15}>
        <section>
          <nav className="detail-tabs" role="tablist" aria-label="歌单内容">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "songs"}
              className={`detail-tabs__item${tab === "songs" ? " detail-tabs__item--active" : ""}`}
              onClick={() => setTab("songs")}
            >
              歌曲列表
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "comments"}
              className={`detail-tabs__item${tab === "comments" ? " detail-tabs__item--active" : ""}`}
              onClick={() => setTab("comments")}
            >
              评论
              {playlist.comment_count > 0 && (
                <span className="detail-tabs__count">{playlist.comment_count}</span>
              )}
            </button>
          </nav>

          {tab === "songs" ? (
            sortedMusics.length === 0 ? (
              <EmptyState icon={Music} title="该歌单暂无歌曲" description="歌单创建者可以通过搜索将歌曲添加到歌单。" />
            ) : (
              <StaggerContainer staggerDelay={0.04}>
                {sortedMusics.map((pm) => (
                  <StaggerItem key={`${pm.music.id}-${pm.ordinal}`}>
                    <SongRow
                      name={pm.music.title}
                      artist={formatAuthors(pm.music.authors)}
                      album={formatAlbumTitle(pm.music.albums)}
                      playCount={pm.music.play_count}
                      musicId={pm.music.id}
                      coverUrl={pm.music.cover_icon_url ?? undefined}
                      onPlay={() => handlePlayMusic(pm)}
                    />
                  </StaggerItem>
                ))}
              </StaggerContainer>
            )
          ) : (
            <CommentSection
              targetType="playlist"
              targetId={playlist.id}
              commentCount={playlist.comment_count}
            />
          )}
        </section>
      </FadeIn>

      {/* 编辑弹窗 */}
      <CreatePlaylistModal
        open={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        edit={
          playlist
            ? {
                id: playlist.id,
                title: playlist.title,
                description: playlist.description,
                is_private: playlist.is_private,
                cover_icon_url: playlist.cover_icon_url,
              }
            : undefined
        }
        onUpdated={handleUpdated}
        onDeleted={() => {
          setEditModalOpen(false);
          navigate("/playlists", { replace: true });
        }}
      />

      {/* 删除确认弹窗 */}
      <ConfirmDeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={() => void handleDeleteConfirm()}
        itemType="歌单"
        itemName={playlist?.title ?? ""}
        description="删除后无法恢复，歌单中的歌曲不会被删除。"
        loading={deleting}
      />
    </div>
  );
};
