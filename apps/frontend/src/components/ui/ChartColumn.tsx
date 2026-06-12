import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import type { MusicListItem } from "../../shared/api/types";
import { formatAuthors } from "../../shared/utils";

interface ChartColumnProps {
  title: string;
  icon: LucideIcon;
  accent: string;
  songs: MusicListItem[];
  loading?: boolean;
  onViewAll?: () => void;
  onPlay?: (song: MusicListItem) => void;
}

const ACCENT_COLORS: Record<string, { bg: string; text: string }> = {
  coral: { bg: "color-mix(in srgb, var(--color-brand-coral) 12%, transparent)", text: "var(--color-brand-coral)" },
  pink: { bg: "color-mix(in srgb, var(--color-brand-pink) 12%, transparent)", text: "var(--color-brand-pink)" },
  teal: { bg: "color-mix(in srgb, var(--color-brand-teal) 12%, transparent)", text: "var(--color-brand-teal)" },
  lavender: { bg: "color-mix(in srgb, var(--color-brand-lavender) 20%, transparent)", text: "#7c5fd4" },
  ochre: { bg: "color-mix(in srgb, var(--color-brand-ochre) 20%, transparent)", text: "#c49a20" },
  mint: { bg: "color-mix(in srgb, var(--color-brand-mint) 25%, transparent)", text: "#3a9a82" },
};

export const ChartColumn = ({
  title,
  icon: Icon,
  accent,
  songs,
  loading = false,
  onViewAll,
  onPlay,
}: ChartColumnProps) => {
  const colors = ACCENT_COLORS[accent] ?? ACCENT_COLORS.coral;

  return (
    <div className="chart-column">
      <div className="chart-column-header">
        <div className="chart-column-title-row">
          <span
            className="chart-column-icon"
            style={{ background: colors.bg, color: colors.text }}
          >
            <Icon size={18} />
          </span>
          <h3 className="chart-column-title">{title}</h3>
        </div>
        {onViewAll && (
          <button type="button" className="chart-column-view-all" onClick={onViewAll}>
            查看全部
          </button>
        )}
      </div>

      <div className="chart-column-list">
        {loading ? (
          <div className="chart-column-loading">加载中...</div>
        ) : songs.length === 0 ? (
          <div className="chart-column-empty">暂无数据</div>
        ) : (
          songs.slice(0, 5).map((song, i) => (
            <motion.div
              key={song.id}
              className="chart-song-item"
              onClick={() => onPlay?.(song)}
              whileHover={{ x: 4 }}
              transition={{ duration: 0.15 }}
            >
              <span
                className={`chart-song-index${i < 3 ? " chart-song-index--top" : ""}`}
              >
                {i + 1}
              </span>
              <div className="chart-song-info">
                <div className="chart-song-name">{song.title}</div>
                <div className="chart-song-artist">{formatAuthors(song.authors)}</div>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
};
