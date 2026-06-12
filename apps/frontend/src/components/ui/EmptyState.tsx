import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

type AccentVariant = "pink" | "teal" | "lavender" | "peach" | "ochre" | "mint" | "coral";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  compact?: boolean;
  accent?: AccentVariant;
}

export const EmptyState = ({
  icon: Icon,
  title,
  description,
  action,
  compact = false,
  accent = "lavender",
}: EmptyStateProps) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.96 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
    className="empty-state"
    style={{
      padding: compact ? "32px 20px" : "60px 20px",
    }}
  >
    <motion.div
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ delay: 0.1, duration: 0.4 }}
      className={`icon-accent-bg icon-accent-bg--${accent}`}
      style={{
        width: compact ? 48 : 64,
        height: compact ? 48 : 64,
        borderRadius: "50%",
        marginBottom: 16,
      }}
    >
      <Icon size={compact ? 24 : 32} strokeWidth={1.5} />
    </motion.div>
    <h3>{title}</h3>
    {description && <p>{description}</p>}
    {action && (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        style={{ marginTop: 12 }}
      >
        {action}
      </motion.div>
    )}
  </motion.div>
);
