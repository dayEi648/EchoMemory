import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ListMusic } from "lucide-react";

import { playlistApi } from "../shared/api/instances";
import type { PlaylistListItem } from "../shared/api/types";
import { CoverCard } from "../components/ui/CoverCard";
import { SectionHeader } from "../components/ui/SectionHeader";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { PaginationBar } from "../components/ui/PaginationBar";

const categories = ["全部", "流行", "摇滚", "电子", "轻音乐", "学习", "睡眠", "运动", "派对"];

const PAGE_SIZE = 12;

export const PlaylistsPage = () => {
  const navigate = useNavigate();
  const [activeCat, setActiveCat] = useState("全部");

  const [playlists, setPlaylists] = useState<PlaylistListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);

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

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">播放列表广场</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div style={{ display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap" }}>
          {categories.map((cat) => (
            <motion.button
              key={cat}
              className={`tag-pill ${cat === activeCat ? "active" : ""}`}
              onClick={() => setActiveCat(cat)}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              type="button"
            >
              {cat}
            </motion.button>
          ))}
        </div>
      </FadeIn>

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
          />
        </FadeIn>
      ) : (
        <>
          <section style={{ marginBottom: 32 }}>
            <SectionHeader title="我的歌单" />
            <StaggerContainer className="playlist-rail">
              {playlists.map((p) => (
                <StaggerItem key={p.id}>
                  <CoverCard
                    id={p.id}
                    title={p.title}
                    subtitle={`${p.user.nickname}${p.is_private ? " · 私密" : ""}`}
                    coverUrl={p.cover_icon_url ?? undefined}
                    onClick={() => navigate(`/playlist/${p.id}`)}
                  />
                </StaggerItem>
              ))}
            </StaggerContainer>
          </section>

          {(totalPages > 1 || total > 0) && (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              loading={loading}
              total={total}
            />
          )}
        </>
      )}
    </div>
  );
};
