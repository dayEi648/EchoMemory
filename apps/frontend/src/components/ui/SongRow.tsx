import { motion } from "framer-motion";
import { Play, Heart } from "lucide-react";
import { useState } from "react";

interface SongRowProps {
  index: number;
  name: string;
  artist: string;
  album?: string;
  duration?: string;
  showHeart?: boolean;
}

export const SongRow = ({
  index,
  name,
  artist,
  album,
  duration,
  showHeart = false,
}: SongRowProps) => {
  const [hovered, setHovered] = useState(false);

  const isTop3 = index <= 2;
  const rankColors = ["var(--color-accent)", "#b8860b", "#a0522d"];

  return (
    <div
      className="song-row"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span
        className="song-index"
        style={{
          fontWeight: isTop3 ? 700 : 400,
          color: isTop3 ? rankColors[index] : "var(--color-muted)",
        }}
      >
        {hovered ? (
          <motion.span
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.15 }}
          >
            <Play size={14} fill="var(--color-ink)" />
          </motion.span>
        ) : (
          index + 1
        )}
      </span>
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
