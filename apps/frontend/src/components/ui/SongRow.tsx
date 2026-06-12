import { motion } from "framer-motion";
import { Play, Heart, Music } from "lucide-react";
import { useState } from "react";
import { usePlayerStore } from "../../shared/stores/playerStore";
import { usePlayerViewStore } from "../../shared/stores/playerViewStore";

interface SongRowProps {
  index: number;
  name: string;
  artist: string;
  album?: string;
  duration?: string;
  showHeart?: boolean;
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
  index,
  name,
  artist,
  album,
  duration,
  showHeart = false,
  musicId,
  coverUrl,
  isPlaying: isPlayingProp,
  onPlay,
}: SongRowProps) => {
  const [hovered, setHovered] = useState(false);
  const [coverError, setCoverError] = useState(false);
  const openPlayerView = usePlayerViewStore((s) => s.open);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id);
  const playerIsPlaying = usePlayerStore((s) => s.isPlaying);
  const isPlaying =
    isPlayingProp ?? (musicId !== undefined && currentTrackId === musicId && playerIsPlaying);

  const isTop3 = index <= 2;

  const handleClick = () => {
    if (musicId !== undefined) {
      openPlayerView(musicId);
    }
  };

  return (
    <div
      className={`song-row${isPlaying ? " playing" : ""}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{ cursor: musicId ? "pointer" : "default" }}
    >
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
            onClick={(e) => {
              e.stopPropagation();
              onPlay?.();
            }}
            style={{ cursor: "pointer", display: "inline-flex", color: "var(--color-brand-coral)" }}
          >
            <Play size={14} fill="currentColor" />
          </motion.span>
        ) : (
          index + 1
        )}
      </span>
      {coverUrl && !coverError ? (
        <img
          src={coverUrl}
          alt={name}
          onError={() => setCoverError(true)}
          style={{
            width: 40,
            height: 40,
            borderRadius: 8,
            objectFit: "cover",
            flexShrink: 0,
          }}
        />
      ) : coverUrl ? (
        <div
          aria-hidden
          className="icon-accent-bg icon-accent-bg--lavender"
          style={{
            width: 40,
            height: 40,
            flexShrink: 0,
          }}
        >
          <Music size={16} />
        </div>
      ) : null}
      <div className="song-info">
        <div className="song-name">{name}</div>
        <div className="song-artist">{artist}</div>
      </div>
      {album && <span className="song-album">{album}</span>}
      {(duration || showHeart) && (
        <span className="song-duration">
          {showHeart && hovered ? (
            <motion.span
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.15 }}
              style={{ color: "var(--color-brand-pink)" }}
            >
              <Heart size={14} />
            </motion.span>
          ) : (
            duration
          )}
        </span>
      )}
    </div>
  );
};
