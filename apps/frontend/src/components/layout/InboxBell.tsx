import { useState, useRef, useEffect } from "react";
import { Bell, Mail, ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

import { useInboxStore } from "../../shared/stores/inboxStore";
import { useAuthStore } from "../../shared/stores/authStore";
import {
  NOTIFICATION_ICON_MAP,
  NOTIFICATION_LABEL_MAP,
  formatBadge,
} from "../../shared/notificationHelpers";

export const InboxBell = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"notifications" | "messages">("notifications");
  const ref = useRef<HTMLDivElement>(null);
  const { user } = useAuthStore();
  const {
    unread,
    notifications,
    conversations,
    refreshUnread,
    loadNotifications,
    loadConversations,
    markNotificationRead,
  } = useInboxStore();

  const totalUnread = (unread?.notification_unread ?? 0) + (unread?.message_unread ?? 0);

  useEffect(() => {
    if (open) {
      void refreshUnread();
      void loadNotifications();
      void loadConversations();
    }
  }, [open, refreshUnread, loadNotifications, loadConversations]);

  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  if (!user) return null;

  const handleViewAll = () => {
    setOpen(false);
    navigate(`/messages?tab=${tab}`);
  };

  const handleNotificationClick = async (notifId: number) => {
    await markNotificationRead(notifId);
    setOpen(false);
  };

  return (
    <div ref={ref} style={{ position: "relative" }}>
      {/* Bell button */}
      <motion.button
        className="action-button"
        onClick={() => setOpen(!open)}
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.92 }}
        type="button"
        title="通知与私信"
        style={{ position: "relative" }}
      >
        <Bell size={18} />
        {totalUnread > 0 && (
          <span
            style={{
              position: "absolute",
              top: 2,
              right: 2,
              minWidth: 16,
              height: 16,
              padding: "0 4px",
              borderRadius: 8,
              background: "var(--color-brand-coral)",
              color: "white",
              fontSize: 10,
              fontWeight: 700,
              lineHeight: "16px",
              textAlign: "center",
            }}
          >
            {formatBadge(totalUnread)}
          </span>
        )}
      </motion.button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="inbox-dropdown"
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.18, ease: [0.25, 0.1, 0.25, 1] }}
          >
            {/* Tabs */}
            <div className="inbox-tabs">
              <button
                type="button"
                className={`inbox-tab ${tab === "notifications" ? "active" : ""}`}
                onClick={() => setTab("notifications")}
              >
                <Bell size={14} />
                通知
                {unread.notification_unread > 0 && (
                  <span className="inbox-tab-badge">{unread.notification_unread}</span>
                )}
              </button>
              <button
                type="button"
                className={`inbox-tab ${tab === "messages" ? "active" : ""}`}
                onClick={() => setTab("messages")}
              >
                <Mail size={14} />
                私信
                {unread.message_unread > 0 && (
                  <span className="inbox-tab-badge">{unread.message_unread}</span>
                )}
              </button>
            </div>

            {/* Content */}
            <div className="inbox-dropdown-body">
              {tab === "notifications" &&
                (notifications.length === 0 ? (
                  <div className="inbox-empty">暂无新通知</div>
                ) : (
                  notifications.slice(0, 5).map((n) => {
                    const Icon = NOTIFICATION_ICON_MAP[n.type] ?? Bell;
                    const label = NOTIFICATION_LABEL_MAP[n.type] ?? "互动通知";
                    return (
                      <button
                        key={n.id}
                        type="button"
                        className={`inbox-item ${!n.is_read ? "inbox-item--unread" : ""}`}
                        onClick={() => handleNotificationClick(n.id)}
                      >
                        <span className={`inbox-item-icon icon-accent-bg icon-accent-bg--${n.type === 0 ? "teal" : n.type === 1 ? "lavender" : "coral"}`}>
                          <Icon size={14} />
                        </span>
                        <span className="inbox-item-text">
                          <span className="inbox-item-actor">
                            {n.actor?.nickname ?? "系统"}
                          </span>
                          {" "}
                          {label}
                        </span>
                        {!n.is_read && <span className="inbox-dot" />}
                      </button>
                    );
                  })
                ))}

              {tab === "messages" &&
                (conversations.length === 0 ? (
                  <div className="inbox-empty">暂无新私信</div>
                ) : (
                  conversations.slice(0, 5).map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      className={`inbox-item ${c.unread_count > 0 ? "inbox-item--unread" : ""}`}
                      onClick={() => {
                        setOpen(false);
                        navigate("/messages");
                      }}
                    >
                      <span className="inbox-item-avatar">
                        {c.peer.avatar_url ? (
                          <img src={c.peer.avatar_url} alt={c.peer.nickname} />
                        ) : (
                          <span className="inbox-item-avatar-fallback">
                            {c.peer.nickname.slice(0, 1)}
                          </span>
                        )}
                      </span>
                      <span className="inbox-item-text">
                        <span className="inbox-item-actor">
                          {c.peer.nickname}
                          {c.peer.is_official && (
                            <span className="official-badge-sm">官方</span>
                          )}
                        </span>
                        <span className="inbox-item-preview">
                          {c.last_message?.content ?? "暂无消息"}
                        </span>
                      </span>
                      {c.unread_count > 0 && (
                        <span className="inbox-badge-count">{formatBadge(c.unread_count)}</span>
                      )}
                    </button>
                  ))
                ))}
            </div>

            {/* Footer */}
            <button type="button" className="inbox-view-all" onClick={handleViewAll}>
              查看全部
              <ArrowUpRight size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
