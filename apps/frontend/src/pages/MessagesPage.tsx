import { useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Bell,
  Send,
  MoreVertical,
  Ban,
  CheckCheck,
  MessageCircle,
  ShieldAlert,
  FileText,
  Bot,
  UserCheck,
} from "lucide-react";
import { Modal } from "../components/ui/Modal";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { useInboxStore } from "../shared/stores/inboxStore";
import { useAuthStore } from "../shared/stores/authStore";
import type { NotificationItem, DirectMessageItem } from "../shared/api/types";
import {
  NOTIFICATION_ICON_MAP,
  NOTIFICATION_LABEL_MAP,
  formatBadge,
} from "../shared/notificationHelpers";
import { formatRelativeTime } from "../shared/utils";
import { appealApi } from "../shared/api/instances";
import { getApiErrorMessage } from "../shared/apiError";

/* ================================================================
 * Notification Panel
 * ================================================================ */
const MODERATION_ACTION_LABELS: Record<string, string> = {
  deleted: "内容已被移除",
  sanitized: "内容已被清除",
  hidden_after_failures: "审核失败，内容已暂时隐藏",
};

const CONTENT_TYPE_LABELS: Record<string, string> = {
  comment: "评论",
  space_post: "说说",
  playlist: "歌单",
  user_profile: "个人资料",
};

function NotificationPanel() {
  const navigate = useNavigate();
  const { notifications, markNotificationRead, markAllNotificationsRead } =
    useInboxStore();
  const [moderationDetail, setModerationDetail] =
    useState<NotificationItem | null>(null);

  const handleClick = async (n: NotificationItem) => {
    if (!n.is_read) {
      await markNotificationRead(n.id);
    }
    if (n.type === 5) {
      setModerationDetail(n);
      return;
    }
    if (n.type === 0 && n.actor) {
      navigate(`/profile/${n.actor.id}`);
    } else if (n.type === 1 || n.type === 2) {
      navigate(`/space`);
    } else if (n.type === 3 || n.type === 4) {
      navigate(`/space`);
    }
  };

  return (
    <div className="notification-panel">
      <div className="notification-panel-header">
        <h3>通知中心</h3>
        <button
          type="button"
          className="ghost-button"
          onClick={() => void markAllNotificationsRead()}
        >
          <CheckCheck size={14} />
          全部已读
        </button>
      </div>
      <div className="notification-panel-list">
        {notifications.length === 0 ? (
          <div className="empty-state">
            <h3>暂无通知</h3>
            <p>当有人与你互动时，通知会出现在这里</p>
          </div>
        ) : (
          notifications.map((n) => {
            const Icon = NOTIFICATION_ICON_MAP[n.type] ?? Bell;
            const baseLabel = NOTIFICATION_LABEL_MAP[n.type] ?? "互动通知";
            const extra = (n.extra ?? {}) as Record<string, unknown>;
            const label =
              n.type === 5
                ? MODERATION_ACTION_LABELS[String(extra.action ?? "")] ?? baseLabel
                : baseLabel;
            const iconAccent =
              n.type === 5 ? "pink" : n.type === 0 ? "teal" : n.type === 1 ? "lavender" : "coral";

            return (
              <div
                key={n.id}
                className={`notification-panel-item ${!n.is_read ? "notification-panel-item--unread" : ""}`}
                onClick={() => void handleClick(n)}
              >
                <span
                  className={`notification-panel-item__icon icon-accent-bg icon-accent-bg--${iconAccent}`}
                >
                  <Icon size={16} />
                </span>
                <div className="notification-panel-item__content">
                  <div className="notification-panel-item__text">
                    <span className="notification-panel-item__actor">
                      {n.actor?.nickname ?? "系统"}
                    </span>
                    {" "}
                    {label}
                  </div>
                  {n.type === 5 && extra.content_preview ? (
                    <div
                      className="notification-panel-item__time"
                      style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        maxWidth: 240,
                        marginTop: 2,
                      }}
                    >
                      「{String(extra.content_preview)}」
                    </div>
                  ) : (
                    <div className="notification-panel-item__time">
                      {formatRelativeTime(n.created_at)}
                    </div>
                  )}
                </div>
                {!n.is_read && <span className="notification-panel-item__dot" />}
              </div>
            );
          })
        )}
      </div>

      {/* 审核详情弹窗 */}
      <Modal
        open={moderationDetail !== null}
        onClose={() => setModerationDetail(null)}
        title="审核详情"
        maxWidth={480}
      >
        {moderationDetail && (
          <ModerationDetailContent notification={moderationDetail} />
        )}
      </Modal>
    </div>
  );
}

/** 审核通知详情内容 */
function ModerationDetailContent({
  notification,
}: {
  notification: NotificationItem;
}) {
  const extra = (notification.extra ?? {}) as Record<string, unknown>;
  const action = String(extra.action ?? "unknown");
  const reason = String(extra.reason ?? "无");
  const safetyLevel = String(extra.safety_level ?? "");
  const source = String(extra.source ?? "AGENT");
  const contentType = String(extra.content_type ?? notification.target_type);
  const preview = String(extra.content_preview ?? "");
  const [appealing, setAppealing] = useState(false);
  const [appealReason, setAppealReason] = useState("");

  const handleAppeal = async () => {
    setAppealing(true);
    try {
      await appealApi.create({
        content_type: contentType,
        content_id: notification.target_id,
        appeal_reason: appealReason || null,
      });
      toast.success("申诉已提交，管理员将尽快处理");
      setAppealReason("");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "申诉提交失败"));
    } finally {
      setAppealing(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {preview && (
        <div>
          <div style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 6, fontWeight: 600 }}>
            涉及内容（{CONTENT_TYPE_LABELS[contentType] ?? contentType}）
          </div>
          <div
            style={{
              padding: "10px 12px", borderRadius: 8, background: "var(--color-surface-soft)",
              fontSize: 13, lineHeight: 1.6, color: "var(--color-body)", wordBreak: "break-word",
            }}
          >
            {preview}
          </div>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ShieldAlert size={16} style={{ color: "var(--color-brand-coral)" }} />
        <span style={{ fontSize: 14, fontWeight: 600, color: "var(--color-ink)" }}>
          {MODERATION_ACTION_LABELS[action] ?? action}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
        <DetailChip label="安全档位" value={safetyLevel || "—"} />
        <DetailChip
          label="审核来源"
          value={source === "MANUAL" ? "人工审核" : "AI 自动审核"}
          icon={source === "MANUAL" ? UserCheck : Bot}
        />
      </div>

      <div>
        <div style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 6, fontWeight: 600 }}>审核理由</div>
        <div
          style={{
            padding: "10px 12px", borderRadius: 8, background: "var(--color-surface-soft)",
            fontSize: 13, lineHeight: 1.6, color: "var(--color-body)",
          }}
        >
          {reason}
        </div>
      </div>

      {/* 申诉入口 */}
      {action !== "appeal_approved" && action !== "appeal_denied" && (
        <div
          style={{
            borderTop: "1px solid var(--color-hairline)",
            paddingTop: 12,
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div style={{ fontSize: 12, color: "var(--color-muted)", fontWeight: 600 }}>
            认为处理有误？
          </div>
          <textarea
            value={appealReason}
            onChange={(e) => setAppealReason(e.target.value)}
            placeholder="申诉理由（可选）"
            rows={2}
            disabled={appealing}
            style={{
              width: "100%",
              minHeight: 44,
              padding: "8px 12px",
              border: "1px solid var(--color-hairline)",
              borderRadius: 8,
              fontSize: 13,
              resize: "vertical",
              background: "var(--color-canvas)",
            }}
          />
          <button
            type="button"
            className="primary-button"
            onClick={() => void handleAppeal()}
            disabled={appealing}
            style={{ alignSelf: "flex-end", fontSize: 13, padding: "6px 16px", minHeight: 34 }}
          >
            {appealing ? "提交中..." : "提交申诉"}
          </button>
        </div>
      )}

      <div style={{ fontSize: 12, color: "var(--color-muted-soft)" }}>
        {formatRelativeTime(notification.created_at)}
      </div>
    </div>
  );
}

function DetailChip({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon?: React.ComponentType<{ size?: number }>;
}) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--color-muted)", marginBottom: 2 }}>
        {label}
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: "var(--color-ink)",
          display: "flex",
          alignItems: "center",
          gap: 4,
        }}
      >
        {Icon && <Icon size={14} />}
        {value}
      </div>
    </div>
  );
}

/* ================================================================
 * Chat Panel
 * ================================================================ */
function ChatPanel({ conversationId }: { conversationId: number }) {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    currentMessages,
    conversations,
    selectConversation,
    sendMessage,
    loadMessages,
    blockUser,
    unblockUser,
  } = useInboxStore();
  const [input, setInput] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesListRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(1);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const conv = conversations.find((c) => c.id === conversationId);
  const peer = conv?.peer;

  // 加载
  useEffect(() => {
    void selectConversation(conversationId);
  }, [conversationId]); // eslint-disable-line react-hooks/exhaustive-deps

  // 滚动到底部
  useEffect(() => {
    if (page === 1) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentMessages.length, page]);

  // 加载更多历史消息
  const handleLoadMore = useCallback(async () => {
    const nextPage = page + 1;
    setPage(nextPage);
    await loadMessages(conversationId, { limit: 50, offset: nextPage * 50 });
  }, [conversationId, loadMessages, page]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || !peer || !user) return;
    // 如果屏蔽了对方，先取消屏蔽再发
    if (conv?.is_blocked_by_me) {
      await unblockUser(peer.id);
    }
    await sendMessage(peer.id, trimmed);
    setInput("");
    inputRef.current?.focus();
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const handleBlock = async () => {
    if (!peer) return;
    setMenuOpen(false);
    if (conv?.is_blocked_by_me) {
      await unblockUser(peer.id);
    } else {
      await blockUser(peer.id);
    }
  };

  if (!peer) {
    return (
      <div className="messages-placeholder">
        选择一个会话开始聊天
      </div>
    );
  }

  const isBlocked =
    conv?.is_blocking_me === true;
  const blockedByMe =
    conv?.is_blocked_by_me === true;

  return (
    <div className="messages-chat-panel">
      {/* Header */}
      <div className="messages-chat-header">
        <div
          className="messages-sidebar-avatar"
          style={{ width: 36, height: 36, cursor: "pointer" }}
          onClick={() => navigate(`/profile/${peer.id}`)}
        >
          {peer.avatar_url ? (
            <img src={peer.avatar_url} alt={peer.nickname} />
          ) : (
            <div className="messages-sidebar-avatar-fallback">
              {peer.nickname.slice(0, 1)}
            </div>
          )}
        </div>
        <span className="messages-chat-header-peer">
          {peer.nickname}
          {peer.is_official && <span className="official-badge-sm">官方</span>}
        </span>

        <div className="messages-chat-header-menu-wrap">
          <button
            type="button"
            className="messages-chat-header-menu-btn"
            onClick={() => setMenuOpen(!menuOpen)}
            title="更多"
          >
            <MoreVertical size={16} />
          </button>
          <AnimatePresence>
            {menuOpen && (
              <motion.div
                className="messages-chat-header-menu"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.12 }}
              >
                <button type="button" onClick={handleBlock}>
                  <Ban size={13} />
                  {blockedByMe ? "取消屏蔽" : "屏蔽该用户"}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Messages */}
      <div className="messages-chat-messages" ref={messagesListRef}>
        {currentMessages.length > 10 && (
          <div className="messages-load-more">
            <button type="button" onClick={handleLoadMore}>
              加载更多消息
            </button>
          </div>
        )}
        {currentMessages.map((m: DirectMessageItem) => {
          const isMine = m.sender_id === user!.id;
          return (
            <div
              key={m.id}
              className={`message-bubble-row ${isMine ? "message-bubble-row--mine" : "message-bubble-row--theirs"}`}
            >
              <div
                className={`message-bubble ${isMine ? "message-bubble--mine" : "message-bubble--theirs"}`}
              >
                {m.content}
                <div className="message-bubble__time">
                  {new Date(m.created_at).toLocaleTimeString("zh-CN", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="messages-chat-input-wrap">
        <div className="messages-chat-input-row">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isBlocked
                ? "对方已屏蔽你，无法发送消息"
                : blockedByMe
                  ? "你已屏蔽该用户，发送消息将自动取消屏蔽"
                  : "输入消息… (Enter 发送, Shift+Enter 换行)"
            }
            disabled={isBlocked}
            rows={1}
            maxLength={2000}
          />
          <button
            type="button"
            className="messages-chat-input-send"
            onClick={() => void handleSend()}
            disabled={!input.trim() || isBlocked}
            title="发送"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================
 * MessagesPage (main)
 * ================================================================ */
export const MessagesPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const {
    conversations,
    loadConversations,
  } = useInboxStore();
  const initialTab = searchParams.get("tab") ?? "messages";
  const [selectedTab, setSelectedTab] = useState<"notifications" | string>(
    initialTab === "notifications" ? "notifications" : "messages",
  );
  const initialPeerId = searchParams.get("u");

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  // 自动选中 ?u= 指定的用户会话
  useEffect(() => {
    if (initialPeerId) {
      const peerId = Number(initialPeerId);
      const conv = conversations.find(
        (c) => c.peer.id === peerId,
      );
      if (conv) {
        setSelectedTab(conv.id.toString());
      } else {
        setSelectedTab("messages");
      }
    }
  }, [initialPeerId, conversations]);

  const selectedConvId =
    selectedTab !== "notifications" ? Number(selectedTab) : null;

  return (
    <div className="messages-page">
      {/* Sidebar */}
      <div className="messages-sidebar">
        <div className="messages-sidebar-header">
          <span className="text-title-md" style={{ margin: 0 }}>
            消息中心
          </span>
        </div>
        <div className="messages-sidebar-list">
          {/* 通知中心虚拟项 */}
          <button
            type="button"
            className={`messages-sidebar-item messages-sidebar-item--notification ${selectedTab === "notifications" ? "messages-sidebar-item--active" : ""}`}
            onClick={() => setSelectedTab("notifications")}
          >
            <span className="messages-sidebar-avatar">
              <Bell size={20} />
            </span>
            <span className="messages-sidebar-meta">
              <span className="messages-sidebar-name">通知中心</span>
            </span>
          </button>

          {/* 真实会话 */}
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`messages-sidebar-item ${selectedTab === c.id.toString() ? "messages-sidebar-item--active" : ""}`}
              onClick={() => setSelectedTab(c.id.toString())}
            >
              <span
                className="messages-sidebar-avatar"
                style={{ cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/profile/${c.peer.id}`);
                }}
              >
                {c.peer.avatar_url ? (
                  <img src={c.peer.avatar_url} alt={c.peer.nickname} />
                ) : (
                  <div className="messages-sidebar-avatar-fallback">
                    {c.peer.nickname.slice(0, 1)}
                  </div>
                )}
              </span>
              <span className="messages-sidebar-meta">
                <span className="messages-sidebar-name">
                  {c.peer.nickname}
                  {c.peer.is_official && (
                    <span className="official-badge-sm">官方</span>
                  )}
                </span>
                <span className="messages-sidebar-preview">
                  {c.last_message?.content ?? "暂无消息"}
                </span>
              </span>
              {c.unread_count > 0 && (
                <span className="messages-sidebar-unread">
                  {formatBadge(c.unread_count)}
                </span>
              )}
              <span className="messages-sidebar-time">
                {formatRelativeTime(c.updated_at)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Right Panel */}
      {selectedTab === "notifications" ? (
        <NotificationPanel />
      ) : selectedConvId ? (
        <ChatPanel conversationId={selectedConvId} />
      ) : (
        <div className="messages-placeholder">
          <div>
            <MessageCircle size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>选择一个会话或与好友开始聊天</p>
          </div>
        </div>
      )}
    </div>
  );
};
