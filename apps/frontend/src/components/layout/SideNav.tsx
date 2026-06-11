import { NavLink, useLocation } from "react-router-dom";
import { Compass, LayoutList, Heart, Clock, Sparkles, MessageCircle } from "lucide-react";
import { motion } from "framer-motion";

const mainLinks = [
  { to: "/", icon: Compass, label: "发现音乐" },
  { to: "/playlists", icon: LayoutList, label: "播放列表" },
  { to: "/library", icon: Heart, label: "我的收藏" },
  { to: "/history", icon: Clock, label: "最近播放" },
  { to: "/echo", icon: Sparkles, label: "AI 回声" },
];

const communityLinks = [
  { to: "/space", icon: MessageCircle, label: "个人空间" },
];

export const SideNav = () => {
  const location = useLocation();

  return (
    <nav className="side-nav">
      <div className="side-nav-section">
        <div className="side-nav-label">音乐</div>
        {mainLinks.map((link) => {
          const isActive =
            link.to === "/" ? location.pathname === "/" : location.pathname.startsWith(link.to);
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={`side-nav-link ${isActive ? "active" : ""}`}
              end={link.to === "/"}
            >
              <link.icon size={18} />
              <span>{link.label}</span>
              {isActive && (
                <motion.div
                  layoutId="side-nav-indicator"
                  style={{
                    position: "absolute",
                    left: 0,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 3,
                    height: 20,
                    background: "var(--color-accent)",
                    borderRadius: "0 4px 4px 0",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </NavLink>
          );
        })}
      </div>

      <div className="side-nav-section">
        <div className="side-nav-label">社区</div>
        {communityLinks.map((link) => {
          const isActive = location.pathname.startsWith(link.to);
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={`side-nav-link ${isActive ? "active" : ""}`}
            >
              <link.icon size={18} />
              <span>{link.label}</span>
              {isActive && (
                <motion.div
                  layoutId="side-nav-indicator"
                  style={{
                    position: "absolute",
                    left: 0,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 3,
                    height: 20,
                    background: "var(--color-accent)",
                    borderRadius: "0 4px 4px 0",
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
};