import { create } from "zustand";

import { messageApi, notificationApi, API_BASE_URL } from "../api/instances";
import type {
  ConversationItem,
  DirectMessageItem,
  InboxEvent,
  NotificationItem,
  UnreadSummary,
} from "../api/types";
import { createLocalStorageTokenStore } from "../auth/tokenStore";

const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

function deriveWebSocketBaseUrl(apiBaseUrl: string): string {
  // apiBaseUrl 形如 "/api/v1" 或 "https://example.com/api/v1"，转成 ws(s):// 协议同源 + 同前缀
  if (apiBaseUrl.startsWith("http://") || apiBaseUrl.startsWith("https://")) {
    return apiBaseUrl.replace(/^http/, "ws");
  }
  const { protocol, host } = window.location;
  const wsProtocol = protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${host}${apiBaseUrl}`;
}

interface InboxState {
  unread: UnreadSummary;
  notifications: NotificationItem[];
  conversations: ConversationItem[];
  currentConversationId: number | null;
  currentMessages: DirectMessageItem[];

  websocket: WebSocket | null;
  reconnectAttempt: number;
  reconnectTimer: ReturnType<typeof setTimeout> | null;
  manuallyClosed: boolean;

  refreshUnread: () => Promise<void>;
  loadNotifications: () => Promise<void>;
  loadConversations: () => Promise<void>;
  selectConversation: (conversationId: number | null) => Promise<void>;
  loadMessages: (conversationId: number) => Promise<void>;
  markNotificationRead: (notificationId: number) => Promise<void>;
  markAllNotificationsRead: () => Promise<void>;
  markConversationRead: (conversationId: number) => Promise<void>;
  sendMessage: (peerUserId: number, content: string) => Promise<DirectMessageItem | null>;
  blockUser: (userId: number) => Promise<void>;
  unblockUser: (userId: number) => Promise<void>;

  connectWebSocket: () => void;
  disconnectWebSocket: () => void;
  _handleEvent: (event: InboxEvent) => void;
  _scheduleReconnect: () => void;
  reset: () => void;
}

const INITIAL_UNREAD: UnreadSummary = {
  notification_unread: 0,
  message_unread: 0,
};

export const useInboxStore = create<InboxState>((set, get) => ({
  unread: INITIAL_UNREAD,
  notifications: [],
  conversations: [],
  currentConversationId: null,
  currentMessages: [],

  websocket: null,
  reconnectAttempt: 0,
  reconnectTimer: null,
  manuallyClosed: false,

  refreshUnread: async () => {
    try {
      const summary = await notificationApi.getUnreadSummary();
      set({
        unread: {
          notification_unread:
            typeof summary?.notification_unread === "number"
              ? summary.notification_unread
              : 0,
          message_unread:
            typeof summary?.message_unread === "number"
              ? summary.message_unread
              : 0,
        },
      });
    } catch {
      // 网络错误静默忽略，下一次进入相关页面会重新拉取
    }
  },

  loadNotifications: async () => {
    const result = await notificationApi.listNotifications({ limit: 50 });
    set({ notifications: result.items });
  },

  loadConversations: async () => {
    const result = await messageApi.listConversations({ limit: 50 });
    set({ conversations: result.items });
  },

  loadMessages: async (conversationId) => {
    const result = await messageApi.listMessages(conversationId, { limit: 50 });
    // 服务端按时间倒序返回，前端展示需正序
    set({ currentMessages: [...result.items].reverse() });
  },

  selectConversation: async (conversationId) => {
    set({ currentConversationId: conversationId, currentMessages: [] });
    if (conversationId === null) return;
    await get().loadMessages(conversationId);
    await get().markConversationRead(conversationId);
  },

  markNotificationRead: async (notificationId) => {
    await notificationApi.markRead(notificationId);
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === notificationId ? { ...n, is_read: true } : n,
      ),
      unread: {
        ...s.unread,
        notification_unread: Math.max(0, s.unread.notification_unread - 1),
      },
    }));
  },

  markAllNotificationsRead: async () => {
    await notificationApi.markAllRead();
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
      unread: { ...s.unread, notification_unread: 0 },
    }));
  },

  markConversationRead: async (conversationId) => {
    const target = get().conversations.find((c) => c.id === conversationId);
    if (!target || target.unread_count === 0) return;
    await messageApi.markRead(conversationId);
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.id === conversationId ? { ...c, unread_count: 0 } : c,
      ),
      unread: {
        ...s.unread,
        message_unread: Math.max(0, s.unread.message_unread - target.unread_count),
      },
    }));
  },

  sendMessage: async (peerUserId, content) => {
    const trimmed = content.trim();
    if (!trimmed) return null;
    const message = await messageApi.sendMessage(peerUserId, trimmed);
    set((s) => {
      const exists = s.conversations.find((c) => c.id === message.conversation_id);
      const isCurrent = s.currentConversationId === message.conversation_id;
      const updatedConvs = exists
        ? s.conversations
            .map((c) =>
              c.id === message.conversation_id
                ? { ...c, last_message: message, updated_at: message.created_at }
                : c,
            )
            .sort(
              (a, b) =>
                new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
            )
        : s.conversations;
      const updatedMessages = isCurrent
        ? [...s.currentMessages, message]
        : s.currentMessages;
      return { conversations: updatedConvs, currentMessages: updatedMessages };
    });
    if (!get().conversations.find((c) => c.id === message.conversation_id)) {
      // 新建会话：从服务端补一次会话列表，拿到完整 peer 信息
      await get().loadConversations();
    }
    return message;
  },

  blockUser: async (userId) => {
    await messageApi.blockUser(userId);
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.peer.id === userId ? { ...c, is_blocked_by_me: true } : c,
      ),
    }));
  },

  unblockUser: async (userId) => {
    await messageApi.unblockUser(userId);
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.peer.id === userId ? { ...c, is_blocked_by_me: false } : c,
      ),
    }));
  },

  connectWebSocket: () => {
    const existing = get().websocket;
    if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
      return;
    }
    const tokenStore = createLocalStorageTokenStore();
    const tokens = tokenStore.get();
    if (!tokens) return;

    const baseUrl = deriveWebSocketBaseUrl(API_BASE_URL);
    const url = `${baseUrl}/ws/inbox?token=${encodeURIComponent(tokens.accessToken)}`;
    set({ manuallyClosed: false });

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      get()._scheduleReconnect();
      return;
    }

    ws.addEventListener("open", () => {
      set({ websocket: ws, reconnectAttempt: 0 });
      // 连接成功后主动同步一次未读数，弥补连接窗口期内的事件
      void get().refreshUnread();
    });
    ws.addEventListener("message", (raw) => {
      try {
        const event = JSON.parse(raw.data) as InboxEvent;
        get()._handleEvent(event);
      } catch {
        // 忽略非法 JSON
      }
    });
    ws.addEventListener("close", () => {
      set({ websocket: null });
      if (!get().manuallyClosed) {
        get()._scheduleReconnect();
      }
    });
    ws.addEventListener("error", () => {
      // close 事件会随后触发，统一在那里处理
    });

    set({ websocket: ws });
  },

  disconnectWebSocket: () => {
    const timer = get().reconnectTimer;
    if (timer) {
      clearTimeout(timer);
    }
    const ws = get().websocket;
    set({ manuallyClosed: true, reconnectTimer: null, reconnectAttempt: 0 });
    if (ws && ws.readyState <= WebSocket.OPEN) {
      ws.close();
    }
    set({ websocket: null });
  },

  _handleEvent: (event) => {
    if (event.type === "notification") {
      set((s) => ({
        unread: {
          ...s.unread,
          notification_unread: s.unread.notification_unread + 1,
        },
      }));
      // 通知列表当前页可见时同步刷新；否则下次打开会重新拉取
      void get().loadNotifications();
    } else if (event.type === "message") {
      set((s) => {
        const isCurrent = s.currentConversationId === event.conversation_id;
        const newMessage: DirectMessageItem = {
          id: event.message_id,
          conversation_id: event.conversation_id,
          sender_id: event.sender_id,
          content: event.content,
          created_at: new Date().toISOString(),
        };
        const conversations = s.conversations.map((c) =>
          c.id === event.conversation_id
            ? {
                ...c,
                last_message: newMessage,
                unread_count: isCurrent ? 0 : c.unread_count + 1,
                updated_at: newMessage.created_at,
              }
            : c,
        );
        // 若是新会话，前端尚未拉到该 conversation 元数据 → 后台静默 refresh
        const exists = s.conversations.some((c) => c.id === event.conversation_id);
        const reordered = [...conversations].sort(
          (a, b) =>
            new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        );
        const updatedMessages = isCurrent
          ? [...s.currentMessages, newMessage]
          : s.currentMessages;
        const messageUnreadDelta = isCurrent ? 0 : 1;
        if (!exists) {
          // 新会话，异步补全
          void get().loadConversations();
        }
        return {
          conversations: reordered,
          currentMessages: updatedMessages,
          unread: {
            ...s.unread,
            message_unread: s.unread.message_unread + messageUnreadDelta,
          },
        };
      });
      // 当前正打开该会话时，立刻把已读状态同步到后端
      if (get().currentConversationId === event.conversation_id) {
        void messageApi.markRead(event.conversation_id).catch(() => {});
      }
    }
  },

  _scheduleReconnect: () => {
    const attempt = get().reconnectAttempt + 1;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** (attempt - 1), RECONNECT_MAX_MS);
    const timer = setTimeout(() => {
      set({ reconnectTimer: null });
      get().connectWebSocket();
    }, delay);
    set({ reconnectAttempt: attempt, reconnectTimer: timer });
  },

  reset: () => {
    get().disconnectWebSocket();
    set({
      unread: INITIAL_UNREAD,
      notifications: [],
      conversations: [],
      currentConversationId: null,
      currentMessages: [],
    });
  },
}));
