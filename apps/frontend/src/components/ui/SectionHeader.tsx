import { motion } from "framer-motion";
import type { ReactNode } from "react";

interface SectionHeaderProps {
  title: ReactNode;
  action?: ReactNode;
}

export const SectionHeader = ({ title, action }: SectionHeaderProps) => (
  <motion.div
    className="section-header"
    initial={{ opacity: 0, x: -8 }}
    animate={{ opacity: 1, x: 0 }}
    transition={{ duration: 0.35, ease: [0.25, 0.1, 0.25, 1] }}
  >
    <h3>{title}</h3>
    {action}
  </motion.div>
);
