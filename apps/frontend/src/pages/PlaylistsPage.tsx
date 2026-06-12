import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ListMusic, Plus, Pencil, Trash2 } from "lucide-react";
import { motion } from "framer-motion";

import { playlistApi } from "../shared/api/instances";
import type { PlaylistListItem } from "../shared/api/types";
import { CoverCard } from "../components/ui/CoverCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { PaginationBar } from "../components/ui/PaginationBar";
import { CreatePlaylistModal } from "../components/ui/CreatePlaylistModal";
import { ConfirmDeleteModal } from "../components/ui/ConfirmDeleteModal";
import { PaginatedPageLayout } from "../components/layout/PaginatedPageLayout";
import { PageTitle } from "../components/ui/PageTitle";

const PAGE_SIZE = 12;

const CreatePlaylistButton = ({ onClick }: { onClick: () => void }) => (
  <motion.button
    className="btn-primary"
    onClick={onClick}
    whileHover={{ scale: 1.03 }}
    whileTap={{ scale: 0.97 }}
    type="button"
    style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
  >
    <Plus size={16} />
    创建歌单
  </motion.button>
);

export const PlaylistsPage = () => {
  const navigate = useNavigate();
  const [playlists, setPlaylists] = useState<PlaylistListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editPlaylist, setEditPlaylist] = useState<PlaylistListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PlaylistListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadPlaylists = useCallback(async () => {
    setLoading(true);
    try {
      const result = await playlistApi.listPlaylists({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setPlaylists(result.items);
      setTotal(result.total);
    } catch {
      toast.error("加载歌单失败");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    loadPlaylists();
  }, [loadPlaylists]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const handlePlaylistCreated = (playlist: PlaylistListItem) => {
    if (page === 0) {
      setPlaylists((prev) => {
        const filtered = prev.filter((item) => item.id !== playlist.id);
        const likeIndex = filtered.findIndex((item) => item.is_like);
        if (likeIndex >= 0) {
          const next = [...filtered];
          next.splice(likeIndex + 1, 0, playlist);
          return next.slice(0, PAGE_SIZE);
        }
        return [playlist, ...filtered].slice(0, PAGE_SIZE);
      });
      setTotal((prev) => prev + 1);
      return;
    }
    setPage(0);
  };

  const handleUpdated = (updated: PlaylistListItem) => {
    setPlaylists((prev) =>
      prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
    );
    setEditPlaylist(null);
  };

  const handleEditDeleted = (deletedId: number) => {
    setPlaylists((prev) => prev.filter((item) => item.id !== deletedId));
    setTotal((prev) => prev - 1);
    setEditPlaylist(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await playlistApi.deletePlaylist(deleteTarget.id);
      toast.success("歌单已删除");
      setPlaylists((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      setTotal((prev) => prev - 1);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const formatPlaylistSubtitle = (playlist: PlaylistListItem) => {
    const tags = [playlist.user.nickname];
    if (playlist.is_like) tags.push("系统");
    if (playlist.is_private) tags.push("私密");
    return tags.join(" · ");
  };

  const openCreateModal = () => setCreateModalOpen(true);

  return (
    <>
      <PaginatedPageLayout
        header={(
          <FadeIn>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 20,
                gap: 12,
              }}
            >
              <PageTitle icon={ListMusic} iconAccent="lavender">我的歌单</PageTitle>
              <CreatePlaylistButton onClick={openCreateModal} />
            </div>
          </FadeIn>
        )}
        footer={
          (totalPages > 1 || total > 0) ? (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              loading={loading}
              total={total}
            />
          ) : undefined
        }
      >
        {loading ? (
          <div className="loading-screen" style={{ height: "30vh" }}>
            <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
          </div>
        ) : playlists.length === 0 ? (
          <FadeIn delay={0.15}>
            <EmptyState
              icon={ListMusic}
              title="暂无歌单"
              description="你还没有创建任何歌单。创建你的第一个歌单，开始收藏喜欢的音乐。"
              action={<CreatePlaylistButton onClick={openCreateModal} />}
            />
          </FadeIn>
        ) : (
          <section>
            <SectionHeader title="我的歌单" />
            <StaggerContainer className="playlist-rail">
              {playlists.map((p) => (
                <StaggerItem key={p.id}>
                  <div className="playlist-card-wrapper">
                    <CoverCard
                      id={p.id}
                      title={p.title}
                      subtitle={formatPlaylistSubtitle(p)}
                      coverUrl={p.cover_icon_url ?? undefined}
                      onClick={() => navigate(`/playlist/${p.id}`)}
                    />
                    {!p.is_like && (
                      <div className="playlist-card-actions">
                        <motion.button
                          type="button"
                          className="playlist-card-action-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditPlaylist(p);
                          }}
                          whileTap={{ scale: 0.93 }}
                          title="编辑歌单"
                        >
                          <Pencil size={13} />
                          编辑
                        </motion.button>
                        <motion.button
                          type="button"
                          className="playlist-card-action-btn playlist-card-action-btn--danger"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget(p);
                          }}
                          whileTap={{ scale: 0.93 }}
                          title="删除歌单"
                        >
                          <Trash2 size={13} />
                          删除
                        </motion.button>
                      </div>
                    )}
                  </div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </section>
        )}
      </PaginatedPageLayout>

      <CreatePlaylistModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreated={handlePlaylistCreated}
      />

      <CreatePlaylistModal
        open={editPlaylist != null}
        onClose={() => setEditPlaylist(null)}
        edit={
          editPlaylist
            ? { id: editPlaylist.id, title: editPlaylist.title, description: null, is_private: editPlaylist.is_private }
            : undefined
        }
        onUpdated={handleUpdated}
        onDeleted={handleEditDeleted}
      />

      <ConfirmDeleteModal
        open={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDeleteConfirm()}
        itemType="歌单"
        itemName={deleteTarget?.title ?? ""}
        description="删除后无法恢复，歌单中的歌曲不会被删除。"
        loading={deleting}
      />
    </>
  );
};
