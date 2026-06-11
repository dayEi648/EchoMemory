import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Compass, LayoutList, Heart, Clock, Sparkles, MessageCircle, ListMusic, Plus } from "lucide-react";
import { motion } from "framer-motion";

import { playlistApi } from "../../shared/api/instances";
import type { PlaylistListItem } from "../../shared/api/types";
import { CreatePlaylistModal } from "../ui/CreatePlaylistModal";

const mainLinks = [
  { to: "/", icon: Compass, label: "发现音乐" },
  { to: "/playlists", icon: LayoutList, label: "我的歌单" },
  { to: "/library", icon: Heart, label: "我的收藏" },
  { to: "/history", icon: Clock, label: "最近播放" },
  { to: "/echo", icon: Sparkles, label: "AI 回声" },
];

const communityLinks = [
  { to: "/space", icon: MessageCircle, label: "个人空间" },
];

export const SideNav = () => {
  const location = useLocation();
  const [playlists, setPlaylists] = useState<PlaylistListItem[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const loadPlaylists = () => {
    playlistApi
      .listPlaylists({ limit: 20 })
      .then((res) => setPlaylists(res.items ?? []))
      .catch(() => { /* silently fail */ });
  };

  useEffect(() => {
    loadPlaylists();
  }, []);

  const renderNavLink = (to: string, Icon: React.ElementType, label: string) => {
    const isActive =
      to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
    return (
      <NavLink
        key={to}
        to={to}
        className={`side-nav-link ${isActive ? "active" : ""}`}
        end={to === "/"}
      >
        <Icon size={18} />
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
        {isActive && (
          <motion.div
            layoutId="side-nav-indicator"
            style={{
              position: "absolute", left: 0, top: "50%",
              transform: "translateY(-50%)", width: 3, height: 20,
              background: "var(--color-accent)", borderRadius: "0 4px 4px 0",
            }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
        )}
      </NavLink>
    );
  };

  return (
    <nav className="side-nav">
      {/* 音乐 */}
      <div className="side-nav-section">
        <div className="side-nav-label">音乐</div>
        {mainLinks.map((link) => renderNavLink(link.to, link.icon, link.label))}
      </div>

      {/* 我的歌单 */}
      <div className="side-nav-section" style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
        <div className="side-nav-label" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          我的歌单
          <button
            type="button"
            title="创建歌单"
            onClick={() => setCreateModalOpen(true)}
            style={{
              color: "var(--color-muted)",
              padding: 0,
              lineHeight: 1,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
            }}
          >
            <Plus size={14} />
          </button>
        </div>
        <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
          {playlists.length === 0 ? (
            <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--color-muted-soft)" }}>
              暂无歌单
            </div>
          ) : (
            playlists.map((p) => (
              <NavLink
                key={p.id}
                to={`/playlist/${p.id}`}
                className={`side-nav-link ${location.pathname === `/playlist/${p.id}` ? "active" : ""}`}
                end
              >
                <ListMusic size={16} style={{ flexShrink: 0 }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>
                  {p.title}
                </span>
              </NavLink>
            ))
          )}
        </div>
      </div>

      {/* 社区 */}
      <div className="side-nav-section">
        <div className="side-nav-label">社区</div>
        {communityLinks.map((link) => renderNavLink(link.to, link.icon, link.label))}
      </div>

      <CreatePlaylistModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreated={(playlist) => {
          setPlaylists((prev) => [playlist, ...prev.filter((item) => item.id !== playlist.id)].slice(0, 20));
        }}
      />
    </nav>
  );
};
