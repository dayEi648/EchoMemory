import { Music2, Bell, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { motion } from "framer-motion";

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
        <span className="brand-mark-sm" aria-hidden>
          <Music2 size={16} />
        </span>
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
        className={`global-search${focused ? " focused" : ""}`}
        onSubmit={handleSearch}
        animate={{
          boxShadow: focused
            ? "0 0 0 3px rgba(22, 21, 20, 0.08)"
            : "0 0 0 0px rgba(22, 21, 20, 0)",
        }}
        transition={{ duration: 0.2 }}
      >
        <Search size={16} className="search-icon" />
        <input
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="搜索歌曲、歌单、专辑、用户..."
        />
        <button type="submit" className="global-search-submit">
          搜索
        </button>
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
