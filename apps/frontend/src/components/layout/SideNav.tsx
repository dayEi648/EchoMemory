import { useEffect, useState, useRef } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { Compass, LayoutList, Heart, Clock, Sparkles, MessageCircle, ListMusic, Plus, SlidersHorizontal, MoreHorizontal, Pencil, Trash2, Bot } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { playlistApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import type { PlaylistListItem } from "../../shared/api/types";
import { CreatePlaylistModal } from "../ui/CreatePlaylistModal";
import { ConfirmDeleteModal } from "../ui/ConfirmDeleteModal";

const mainLinks = [
  { to: "/", icon: Compass, label: "发现音乐" },
  { to: "/browse", icon: SlidersHorizontal, label: "详细分类" },
  { to: "/playlists", icon: LayoutList, label: "我的歌单" },
  { to: "/library", icon: Heart, label: "我的收藏" },
  { to: "/history", icon: Clock, label: "最近播放" },
  { to: "/echo", icon: Sparkles, label: "个人回声" },
  { to: "/ai-assistant", icon: Bot, label: "AI 助手" },
];

const communityLinks = [
  { to: "/space", icon: MessageCircle, label: "个人空间" },
];

export const SideNav = () => {
  const location = useLocation();
  const [playlists, setPlaylists] = useState<PlaylistListItem[]>([]);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editPlaylist, setEditPlaylist] = useState<PlaylistListItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PlaylistListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const loadPlaylists = () => {
    playlistApi
      .listPlaylists({ limit: 20 })
      .then((res) => setPlaylists(res.items ?? []))
      .catch((err) => {
        toast.error(getApiErrorMessage(err, "加载歌单列表失败"));
      });
  };

  useEffect(() => {
    loadPlaylists();
  }, [location.pathname]);

  // 点击外部关闭菜单
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    };
    if (menuOpenId != null) {
      document.addEventListener("mousedown", handler);
    }
    return () => document.removeEventListener("mousedown", handler);
  }, [menuOpenId]);

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

  const handleEdit = (p: PlaylistListItem) => {
    setMenuOpenId(null);
    setEditPlaylist(p);
  };

  const handleDeleteClick = (p: PlaylistListItem) => {
    setMenuOpenId(null);
    setDeleteTarget(p);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await playlistApi.deletePlaylist(deleteTarget.id);
      setPlaylists((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      toast.success?.("歌单已删除");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除歌单失败"));
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const handleUpdated = (updated: PlaylistListItem) => {
    setPlaylists((prev) =>
      prev.map((item) => (item.id === updated.id ? { ...item, ...updated } : item)),
    );
    setEditPlaylist(null);
  };

  const handleDeleted = (deletedId: number) => {
    setPlaylists((prev) => prev.filter((item) => item.id !== deletedId));
    setEditPlaylist(null);
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
            className="side-nav-add-btn"
            title="创建歌单"
            onClick={() => setCreateModalOpen(true)}
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
              <div
                key={p.id}
                className="side-nav-playlist-item"
                style={{ position: "relative" }}
              >
                <NavLink
                  to={`/playlist/${p.id}`}
                  className={`side-nav-link ${location.pathname === `/playlist/${p.id}` ? "active" : ""}`}
                  end
                  style={{ paddingRight: 32 }}
                >
                  <ListMusic size={16} style={{ flexShrink: 0 }} />
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>
                    {p.title}
                  </span>
                </NavLink>

                {/* 三点菜单按钮 */}
                {!p.is_like && (
                  <button
                    type="button"
                    className="side-nav-playlist-menu-btn"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setMenuOpenId(menuOpenId === p.id ? null : p.id);
                    }}
                    title="更多操作"
                  >
                    <MoreHorizontal size={13} />
                  </button>
                )}

                {/* 下拉菜单 */}
                <AnimatePresence>
                  {menuOpenId === p.id && (
                    <motion.div
                      ref={menuRef}
                      className="side-nav-playlist-dropdown"
                      initial={{ opacity: 0, scale: 0.92, y: -4 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.92, y: -4 }}
                      transition={{ duration: 0.15 }}
                    >
                      <button type="button" onClick={() => handleEdit(p)}>
                        <Pencil size={13} />
                        编辑
                      </button>
                      <button type="button" onClick={() => handleDeleteClick(p)}>
                        <Trash2 size={13} />
                        删除
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 社区 */}
      <div className="side-nav-section">
        <div className="side-nav-label">社区</div>
        {communityLinks.map((link) => renderNavLink(link.to, link.icon, link.label))}
      </div>

      {/* 创建弹窗 */}
      <CreatePlaylistModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreated={(playlist) => {
          setPlaylists((prev) => [playlist, ...prev.filter((item) => item.id !== playlist.id)].slice(0, 20));
        }}
      />

      {/* 编辑弹窗 */}
      <CreatePlaylistModal
        open={editPlaylist != null}
        onClose={() => setEditPlaylist(null)}
        edit={
          editPlaylist
            ? { id: editPlaylist.id, title: editPlaylist.title, description: null, is_private: editPlaylist.is_private, cover_icon_url: editPlaylist.cover_icon_url }
            : undefined
        }
        onUpdated={handleUpdated}
        onDeleted={handleDeleted}
      />

      {/* 删除确认弹窗 */}
      <ConfirmDeleteModal
        open={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDeleteConfirm()}
        itemType="歌单"
        itemName={deleteTarget?.title ?? ""}
        description="删除后无法恢复，歌单中的歌曲不会被删除。"
        loading={deleting}
      />
    </nav>
  );
};
