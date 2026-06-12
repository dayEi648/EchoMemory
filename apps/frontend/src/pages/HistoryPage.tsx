import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { Play, Trash2, Clock, Music } from "lucide-react";
import { toast } from "sonner";

import { playHistoryApi } from "../shared/api/instances";
import type { PlayHistoryItem } from "../shared/api/types";
import { formatRelativeTime } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { FadeIn } from "../components/motion/FadeIn";
import { EmptyState } from "../components/ui/EmptyState";
import { PageTitle } from "../components/ui/PageTitle";
import { PaginationBar } from "../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../components/layout/PaginatedPageLayout";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";

export const HistoryPage = () => {
  const { playMusicById } = usePlayMusic();
  const [history, setHistory] = useState<PlayHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const data = await playHistoryApi.listPlayHistory({
        limit: pageSize,
        offset: page * pageSize,
      });
      setHistory(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch {
      toast.error("加载播放历史失败");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleDelete = async (id: number) => {
    try {
      await playHistoryApi.deletePlayHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
      setTotal((prev) => Math.max(0, prev - 1));
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    }
  };

  const handleClear = async () => {
    if (!confirm("确定要清空全部播放历史吗？此操作不可恢复。")) return;
    try {
      await playHistoryApi.clearPlayHistory();
      setHistory([]);
      setTotal(0);
      setPage(0);
      toast.success("播放历史已清空");
    } catch {
      toast.error("清空失败");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <PaginatedPageLayout
      header={(
        <FadeIn>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <PageTitle icon={Clock} iconAccent="mint">播放历史</PageTitle>
            {history.length > 0 && (
              <motion.button
                className="ghost-button"
                onClick={handleClear}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--color-danger)" }}
              >
                <Trash2 size={14} />
                清空全部
              </motion.button>
            )}
          </div>
        </FadeIn>
      )}
      footer={
        (totalPages > 1 || total > 0) ? (
          <PaginationBar
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            pageSize={pageSize}
            onPageSizeChange={(size) => { setPageSize(size); setPage(0); }}
            loading={loading}
            total={total}
          />
        ) : undefined
      }
    >
      {loading ? (
        <div className="loading-screen" style={{ height: "40vh" }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
        </div>
      ) : history.length === 0 ? (
        <EmptyState icon={Music} title="暂无播放记录" description="开始听歌后，这里会记录你的播放历史。" accent="mint" />
      ) : (
        <StaggerContainer staggerDelay={0.03}>
          {history.map((item) => (
            <StaggerItem key={item.id}>
              <div className="history-row">
                <img
                  src={item.music.cover_icon_url ?? undefined}
                  alt={item.music.title}
                  style={{ width: 48, height: 48, borderRadius: 6, objectFit: "cover", flexShrink: 0 }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.music.title}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--color-muted)", display: "flex", alignItems: "center", gap: 8 }}>
                    <span>未知艺人</span>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <Clock size={12} />
                      {formatRelativeTime(item.played_at)}
                    </span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <motion.button
                    className="player-btn"
                    onClick={() => playMusicById(item.music.id)}
                    whileHover={{ scale: 1.12 }}
                    whileTap={{ scale: 0.92 }}
                    type="button"
                    title="播放"
                  >
                    <Play size={16} fill="var(--color-ink)" />
                  </motion.button>
                  <motion.button
                    className="player-btn"
                    onClick={() => handleDelete(item.id)}
                    whileHover={{ scale: 1.12 }}
                    whileTap={{ scale: 0.92 }}
                    type="button"
                    title="删除"
                  >
                    <Trash2 size={16} />
                  </motion.button>
                </div>
              </div>
            </StaggerItem>
          ))}
        </StaggerContainer>
      )}
    </PaginatedPageLayout>
  );
};
