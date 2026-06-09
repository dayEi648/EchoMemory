import { motion } from "framer-motion";
import { Play } from "lucide-react";

const gradientPairs: [string, string][] = [
  ["#ff9a9e", "#fecfef"],
  ["#a18cd1", "#fbc2eb"],
  ["#84fab0", "#8fd3f4"],
  ["#fccb90", "#d57eeb"],
  ["#e0c3fc", "#8ec5fc"],
  ["#43e97b", "#38f9d7"],
  ["#fa709a", "#fee140"],
  ["#30cfd0", "#330867"],
  ["#a8edea", "#fed6e3"],
  ["#ffecd2", "#fcb69f"],
  ["#667eea", "#764ba2"],
  ["#f093fb", "#f5576c"],
];

function getGradient(id: number): [string, string] {
  const idx = Math.abs(id) % gradientPairs.length;
  return gradientPairs[idx];
}

interface CoverCardProps {
  id: number;
  title: string;
  subtitle: string;
  onClick?: () => void;
}

export const CoverCard = ({ id, title, subtitle, onClick }: CoverCardProps) => {
  const [c1, c2] = getGradient(id);

  return (
    <motion.div
      className="cover-card"
      onClick={onClick}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
    >
      <div className="cover-image">
        <div
          style={{
            width: "100%",
            height: "100%",
            background: `linear-gradient(135deg, ${c1} 0%, ${c2} 100%)`,
            position: "relative",
          }}
        >
          {/* subtle noise texture overlay */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: 0.08,
              backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
              backgroundSize: "128px 128px",
              mixBlendMode: "overlay",
            }}
          />
          {/* decorative circle */}
          <div
            style={{
              position: "absolute",
              bottom: "-20%",
              right: "-20%",
              width: "80%",
              height: "80%",
              borderRadius: "50%",
              background: "rgba(255,255,255,0.12)",
            }}
          />
        </div>
        <div className="cover-overlay">
          <motion.div
            className="play-icon"
            whileHover={{ scale: 1.1 }}
            transition={{ duration: 0.15 }}
          >
            <Play size={18} fill="white" />
          </motion.div>
        </div>
      </div>
      <div className="cover-title">{title}</div>
      <div className="cover-subtitle">{subtitle}</div>
    </motion.div>
  );
};
