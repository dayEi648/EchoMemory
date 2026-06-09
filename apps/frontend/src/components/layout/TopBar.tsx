import { Music2, Bell, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { AvatarMenu } from "./AvatarMenu";

export const TopBar = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [focused, setFocused] = useState(false);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (q) {
      navigate(`/search?q=${encodeURIComponent(q)}`);
    }
  };

  return (
    <header className="top-bar">
      <motion.div
        className="top-bar-brand"
        whileHover={{ scale: 1.02 }}
        style={{ cursor: "pointer" }}
        onClick={() => navigate("/")}
      >
        <Music2 size={20} />
        <span>回声记忆</span>
      </motion.div>

      <div className="top-bar-nav-arrows">
        <motion.button
          className="nav-arrow"
          onClick={() => navigate(-1)}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          type="button"
          title="后退"
        >
          <ChevronLeft size={18} />
        </motion.button>
        <motion.button
          className="nav-arrow"
          onClick={() => navigate(1)}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          type="button"
          title="前进"
        >
          <ChevronRight size={18} />
        </motion.button>
      </div>

      <motion.form
        className="global-search"
        onSubmit={handleSearch}
        animate={{
          boxShadow: focused
            ? "0 0 0 3px rgba(22, 21, 20, 0.08)"
            : "0 0 0 0px rgba(22, 21, 20, 0)",
        }}
        transition={{ duration: 0.2 }}
        style={{ borderRadius: 10 }}
      >
        <Search size={16} className="search-icon" />
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="搜索歌曲、歌单、专辑、用户..."
        />
        <AnimatePresence>
          {searchQuery.trim() && (
            <motion.button
              type="submit"
              initial={{ opacity: 0, scale: 0.8, x: 4 }}
              animate={{ opacity: 1, scale: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.8, x: 4 }}
              transition={{ duration: 0.15 }}
              style={{
                position: "absolute",
                right: 8,
                top: "50%",
                transform: "translateY(-50%)",
                background: "var(--color-ink)",
                color: "white",
                border: "none",
                borderRadius: 6,
                padding: "3px 10px",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              搜索
            </motion.button>
          )}
        </AnimatePresence>
      </motion.form>

      <div className="top-bar-actions">
        <motion.button
          className="action-button"
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.92 }}
          type="button"
          title="通知"
        >
          <Bell size={18} />
        </motion.button>
        <AvatarMenu />
      </div>
    </header>
  );
};
