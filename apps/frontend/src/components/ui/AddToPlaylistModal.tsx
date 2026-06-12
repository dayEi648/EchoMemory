import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ListMusic, Music, Plus } from "lucide-react";
import { toast } from "sonner";

import { playlistApi } from "../../shared/api/instances";
import type { PlaylistMembershipItem } from "../../shared/api/types";
import { Modal } from "./Modal";
import { CreatePlaylistModal } from "./CreatePlaylistModal";

interface AddToPlaylistModalProps {
  open: boolean;
  musicId: number | null;
  onClose: () => void;
  /** 歌曲是否仍存在于任一歌单中（用于同步外部收藏态）。 */
  onCollectedChange?: (collected: boolean) => void;
}

export const AddToPlaylistModal = ({
  open,
  musicId,
  onClose,
  onCollectedChange,
}: AddToPlaylistModalProps) => {
  const [playlists, setPlaylists] = useState<PlaylistMembershipItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const syncCollectedState = useCallback(
    (items: PlaylistMembershipItem[]) => {
      onCollectedChange?.(items.some((item) => item.contains_music));
    },
    [onCollectedChange],
  );

  const loadMembership = useCallback(async () => {
    if (musicId == null) return;
    setLoading(true);
    try {
      const res = await playlistApi.listPlaylistMembershipForMusic(musicId);
      setPlaylists(res.items);
      syncCollectedState(res.items);
    } catch {
      toast.error("加载歌单列表失败");
    } finally {
      setLoading(false);
    }
  }, [musicId, syncCollectedState]);

  useEffect(() => {
    if (!open || musicId == null) {
      setPlaylists([]);
      setTogglingId(null);
      return;
    }
    void loadMembership();
  }, [open, musicId, loadMembership]);

  const handleToggle = async (item: PlaylistMembershipItem) => {
    if (musicId == null || togglingId != null) return;

    setTogglingId(item.id);
    try {
      if (item.contains_music) {
        await playlistApi.removeMusicFromPlaylist(item.id, musicId);
        toast.success(`已从「${item.title}」移除`);
      } else {
        await playlistApi.addMusicToPlaylist(item.id, musicId);
        toast.success(`已添加到「${item.title}」`);
      }

      const next = playlists.map((playlist) =>
        playlist.id === item.id
          ? { ...playlist, contains_music: !playlist.contains_music }
          : playlist,
      );
      setPlaylists(next);
      syncCollectedState(next);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setTogglingId(null);
    }
  };

  const handleCreated = async () => {
    setCreateOpen(false);
    await loadMembership();
  };

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title="添加到歌单"
        maxWidth={440}
      >
        {loading ? (
          <div className="loading-screen" style={{ height: 160 }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
          </div>
        ) : playlists.length === 0 ? (
          <div style={{ textAlign: "center", padding: "24px 0" }}>
            <div
              className="icon-accent-bg icon-accent-bg--lavender"
              style={{ width: 48, height: 48, margin: "0 auto 12px" }}
            >
              <Music size={22} />
            </div>
            <p style={{ margin: "0 0 16px", color: "var(--color-muted)", fontSize: 14 }}>
              你还没有歌单，先创建一个吧
            </p>
            <motion.button
              className="btn-primary"
              type="button"
              whileTap={{ scale: 0.97 }}
              onClick={() => setCreateOpen(true)}
            >
              <Plus size={16} style={{ marginRight: 6 }} />
              创建歌单
            </motion.button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {playlists.map((item) => (
              <motion.button
                key={item.id}
                type="button"
                className="ghost-button"
                disabled={togglingId != null}
                onClick={() => void handleToggle(item)}
                whileTap={{ scale: 0.98 }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 12,
                  border: item.contains_music
                    ? "1px solid var(--color-accent)"
                    : "1px solid var(--color-hairline)",
                  background: item.contains_music
                    ? "color-mix(in srgb, var(--color-accent) 8%, transparent)"
                    : "var(--color-canvas)",
                  textAlign: "left",
                }}
              >
                <div
                  className="icon-accent-bg icon-accent-bg--peach"
                  style={{ width: 36, height: 36, flexShrink: 0 }}
                >
                  {item.cover_icon_url ? (
                    <img
                      src={item.cover_icon_url}
                      alt=""
                      style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: 8 }}
                    />
                  ) : (
                    <ListMusic size={16} />
                  )}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{item.title}</div>
                  <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2 }}>
                    {item.is_like ? "系统歌单" : item.is_private ? "私密" : "公开"}
                  </div>
                </div>
                <div
                  aria-hidden
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: "50%",
                    border: item.contains_music
                      ? "none"
                      : "2px solid var(--color-hairline)",
                    background: item.contains_music ? "var(--color-accent)" : "transparent",
                    flexShrink: 0,
                  }}
                />
              </motion.button>
            ))}

            <motion.button
              type="button"
              className="ghost-button"
              whileTap={{ scale: 0.98 }}
              onClick={() => setCreateOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                marginTop: 4,
                color: "var(--color-muted)",
              }}
            >
              <Plus size={16} />
              新建歌单
            </motion.button>
          </div>
        )}
      </Modal>

      <CreatePlaylistModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => void handleCreated()}
      />
    </>
  );
};
