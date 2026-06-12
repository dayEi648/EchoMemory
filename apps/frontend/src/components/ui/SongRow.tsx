import { motion } from "framer-motion";
import { Play, Heart, Music, BarChart3 } from "lucide-react";
import { useEffect, useState } from "react";
import { usePlayerStore } from "../../shared/stores/playerStore";
import { usePlayerViewStore } from "../../shared/stores/playerViewStore";
import { AddToPlaylistModal } from "./AddToPlaylistModal";

interface SongRowProps {
  /** 列表序号，仅 showIndex 为 true 时展示。 */
  index?: number;
  showIndex?: boolean;
  name: string;
  artist: string;
  album?: string;
  showAlbum?: boolean;
  playCount?: number;
  showCollect?: boolean;
  isCollected?: boolean;
  /** 歌单归属变化时回调（如从全部歌单移除）。 */
  onCollectedChange?: (collected: boolean) => void;
  musicId?: number;
  coverUrl?: string;
  isPlaying?: boolean;
  onPlay?: () => void;
}

const rankColors = [
  "var(--color-brand-coral)",
  "var(--color-brand-ochre)",
  "var(--color-brand-peach)",
];

export const SongRow = ({
  index = 0,
  showIndex = false,
  name,
  artist,
  album,
  showAlbum = true,
  playCount,
  showCollect,
  isCollected,
  onCollectedChange,
  musicId,
  coverUrl,
  isPlaying: isPlayingProp,
  onPlay,
}: SongRowProps) => {
  const [hovered, setHovered] = useState(false);
  const [coverError, setCoverError] = useState(false);
  const [collected, setCollected] = useState(isCollected ?? false);
  const [playlistModalOpen, setPlaylistModalOpen] = useState(false);

  useEffect(() => {
    if (isCollected !== undefined) {
      setCollected(isCollected);
    }
  }, [isCollected]);
  const openPlayerView = usePlayerViewStore((s) => s.open);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id);
  const playerIsPlaying = usePlayerStore((s) => s.isPlaying);
  const isPlaying =
    isPlayingProp ?? (musicId !== undefined && currentTrackId === musicId && playerIsPlaying);

  const isTop3 = showIndex && index <= 2;
  const canCollect = (showCollect ?? musicId != null) && musicId != null;
  const albumLabel =
    showAlbum && album?.trim() ? album.trim() : undefined;

  const handleClick = () => {
    if (musicId !== undefined) {
      openPlayerView(musicId);
      onPlay?.();
    }
  };

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay?.();
  };

  const handleCollectClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPlaylistModalOpen(true);
  };

  return (
    <>
      <div
        className={`song-row${isPlaying ? " playing" : ""}`}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={handleClick}
        style={{ cursor: musicId ? "pointer" : "default" }}
      >
        <div className="song-row-left">
          {showIndex && (
            <span
              className="song-index"
              style={{
                fontWeight: isTop3 || isPlaying ? 700 : 400,
                color: isPlaying
                  ? "var(--color-brand-coral)"
                  : isTop3
                    ? rankColors[index]
                    : "var(--color-muted)",
              }}
            >
              {hovered && onPlay ? (
                <motion.span
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.15 }}
                  onClick={handlePlayClick}
                  style={{ cursor: "pointer", display: "inline-flex", color: "var(--color-brand-coral)" }}
                >
                  <Play size={14} fill="currentColor" />
                </motion.span>
              ) : (
                index + 1
              )}
            </span>
          )}

          <div className="song-cover">
            {coverUrl && !coverError ? (
              <img
                src={coverUrl}
                alt={name}
                onError={() => setCoverError(true)}
              />
            ) : (
              <div aria-hidden className="song-cover-placeholder icon-accent-bg icon-accent-bg--lavender">
                <Music size={16} />
              </div>
            )}
            {!showIndex && hovered && onPlay && (
              <motion.button
                type="button"
                className="song-cover-play"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.15 }}
                onClick={handlePlayClick}
                aria-label="播放"
              >
                <Play size={14} fill="currentColor" />
              </motion.button>
            )}
          </div>

          <div className="song-info">
            <div className="song-name">{name}</div>
            <div className="song-artist">{artist}</div>
          </div>
        </div>

        {albumLabel && (
          <div className="song-album" title={albumLabel}>
            {albumLabel}
          </div>
        )}

        <div className="song-row-actions">
          {canCollect && (
            <button
              type="button"
              className={`song-row-collect${collected ? " active" : ""}`}
              onClick={handleCollectClick}
              title={collected ? "管理歌单" : "收藏"}
              aria-label={collected ? "管理歌单" : "收藏"}
            >
              <Heart size={14} fill={collected ? "currentColor" : "none"} />
            </button>
          )}
          {playCount != null && (
            <span className="song-play-count" title="播放量">
              <BarChart3 size={13} aria-hidden />
              {playCount}
            </span>
          )}
        </div>
      </div>

      {canCollect && (
        <AddToPlaylistModal
          open={playlistModalOpen}
          musicId={musicId}
          onClose={() => setPlaylistModalOpen(false)}
          onCollectedChange={(collected) => {
            setCollected(collected);
            onCollectedChange?.(collected);
          }}
        />
      )}
    </>
  );
};
