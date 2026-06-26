import { NavLink, useLocation } from "react-router-dom";
import { Users, Music, BookOpen, Activity, Disc3, Image, Flame, ScrollText, Bot, MessageSquareText, PanelsTopLeft, Library, ShieldCheck } from "lucide-react";
import { motion } from "framer-motion";

const adminLinks = [
  { to: "/admin", icon: Activity, label: "概览" },
  { to: "/admin/users", icon: Users, label: "用户管理" },
  { to: "/admin/music", icon: Music, label: "音乐管理" },
  { to: "/admin/albums", icon: Disc3, label: "专辑管理" },
  { to: "/admin/carousel", icon: Image, label: "推图管理" },
  { to: "/admin/dict", icon: BookOpen, label: "字典维护" },
  { to: "/admin/hotness", icon: Flame, label: "热度管理" },
  { to: "/admin/comments", icon: MessageSquareText, label: "评论管理" },
  { to: "/admin/space-posts", icon: PanelsTopLeft, label: "说说管理" },
  { to: "/admin/logs", icon: ScrollText, label: "系统日志" },
  { to: "/admin/agent-monitor/ai-conversation", icon: Bot, label: "AI 对话监控" },
  { to: "/admin/agent-monitor/content-moderation", icon: ShieldCheck, label: "内容审核监控" },
  { to: "/admin/music-knowledge", icon: Library, label: "音乐知识库" },
];

export const AdminSideNav = () => {
  const location = useLocation();

  return (
    <nav className="admin-side-nav">
      <div className="side-nav-section">
        <div className="side-nav-label">管理</div>
        {adminLinks.map((link) => {
          const isActive = location.pathname === link.to || (link.to !== "/admin" && location.pathname.startsWith(link.to));
          return (
            <NavLink
              key={link.to}
              to={link.to}
              className={`side-nav-link ${isActive ? "active" : ""}`}
              end={link.to === "/admin"}
              style={{ position: "relative" }}
            >
              <link.icon size={18} />
              <span>{link.label}</span>
              {isActive && (
                <motion.div
                  layoutId="admin-nav-indicator"
                  style={{
                    position: "absolute",
                    left: 0,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 3,
                    height: 20,
                    background: "var(--color-brand-coral)",
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
