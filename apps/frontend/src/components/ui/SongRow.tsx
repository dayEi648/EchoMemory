import { motion } from "framer-motion";
import { Play, Heart, Music } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

interface SongRowProps {
  index: number;
  name: string;
  artist: string;
  album?: string;
  duration?: string;
  showHeart?: boolean;
  musicId?: number;
  coverUrl?: string;
  onPlay?: () => void;
}

export const SongRow = ({
  index,
  name,
  artist,
  album,
  duration,
  showHeart = false,
  musicId,
  coverUrl,
  onPlay,
}: SongRowProps) => {
  const [hovered, setHovered] = useState(false);
  const [coverError, setCoverError] = useState(false);
  const navigate = useNavigate();

  const isTop3 = index <= 2;
  const rankColors = ["var(--color-accent)", "#b8860b", "#a0522d"];

  const handleClick = () => {
    if (musicId) {
      navigate(`/music/${musicId}`);
    }
  };

  return (
    <div
      className="song-row"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={handleClick}
      style={{ cursor: musicId ? "pointer" : "default" }}
    >
      <span
        className="song-index"
        style={{
          fontWeight: isTop3 ? 700 : 400,
          color: isTop3 ? rankColors[index] : "var(--color-muted)",
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
            style={{ cursor: "pointer", display: "inline-flex" }}
          >
            <Play size={14} fill="var(--color-ink)" />
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
            borderRadius: 4,
            objectFit: "cover",
            flexShrink: 0,
          }}
        />
      ) : coverUrl ? (
        <div
          aria-hidden
          style={{
            width: 40,
            height: 40,
            borderRadius: 4,
            flexShrink: 0,
            background: "var(--color-border)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--color-muted)",
            fontSize: 16,
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
