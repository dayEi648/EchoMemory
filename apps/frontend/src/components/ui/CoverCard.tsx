import { motion } from "framer-motion";
import { Play } from "lucide-react";

const brandGradients: [string, string][] = [
  ["var(--color-brand-pink)", "#ff7aa8"],
  ["var(--color-brand-teal)", "#2d5a5a"],
  ["var(--color-brand-lavender)", "#d4c8f5"],
  ["var(--color-brand-peach)", "#ffc9a8"],
  ["var(--color-brand-ochre)", "#f0cc6a"],
  ["var(--color-brand-mint)", "#c4e8dc"],
];

function getGradient(id: number): [string, string] {
  const idx = Math.abs(id) % brandGradients.length;
  return brandGradients[idx];
}

interface CoverCardProps {
  id: number;
  title: string;
  subtitle: string;
  coverUrl?: string;
  onClick?: () => void;
  onPlay?: () => void;
}

export const CoverCard = ({ id, title, subtitle, coverUrl, onClick, onPlay }: CoverCardProps) => {
  const [c1, c2] = getGradient(id);

  return (
    <motion.div
      className="cover-card"
      onClick={onClick}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="cover-image">
        {coverUrl ? (
          <div
            style={{
              width: "100%",
              height: "100%",
              position: "relative",
            }}
          >
            <img
              src={coverUrl}
              alt={title}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
              }}
            />
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "linear-gradient(to top, rgba(0,0,0,0.4) 0%, transparent 50%)",
              }}
            />
          </div>
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              background: `linear-gradient(135deg, ${c1} 0%, ${c2} 100%)`,
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                bottom: "-20%",
                right: "-20%",
                width: "80%",
                height: "80%",
                borderRadius: "50%",
                background: "rgba(255,255,255,0.15)",
              }}
            />
          </div>
        )}
        {onPlay && (
          <div
            className="cover-overlay"
            onClick={(e) => {
              e.stopPropagation();
              onPlay();
            }}
          >
            <motion.div
              className="play-icon"
              whileHover={{ scale: 1.1 }}
              transition={{ duration: 0.15 }}
            >
              <Play size={18} fill="white" />
            </motion.div>
          </div>
        )}
      </div>
      <div className="cover-title">{title}</div>
      <div className="cover-subtitle">{subtitle}</div>
    </motion.div>
  );
};
