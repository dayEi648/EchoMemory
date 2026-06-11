import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ListMusic, Plus } from "lucide-react";
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
import { PaginatedPageLayout } from "../components/layout/PaginatedPageLayout";

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
              <h1 className="page-title" style={{ margin: 0 }}>我的歌单</h1>
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
                  <CoverCard
                    id={p.id}
                    title={p.title}
                    subtitle={formatPlaylistSubtitle(p)}
                    coverUrl={p.cover_icon_url ?? undefined}
                    onClick={() => navigate(`/playlist/${p.id}`)}
                  />
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
    </>
  );
};
