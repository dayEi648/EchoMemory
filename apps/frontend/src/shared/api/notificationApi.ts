import type {
  PaginatedNotificationList,
  UnreadSummary,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createNotificationApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 获取未读汇总（通知 + 私信）。 */
    getUnreadSummary: () =>
      request<UnreadSummary>("/notifications/unread-summary"),

    /** 分页获取通知列表。 */
    listNotifications: (
      params: { onlyUnread?: boolean; limit?: number; offset?: number } = {},
    ) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.onlyUnread) {
        query.set("only_unread", "true");
      }
      return request<PaginatedNotificationList>(`/notifications/?${query.toString()}`);
    },

    /** 标记单条通知为已读。 */
    markRead: (notificationId: number) =>
      request<void>(`/notifications/${notificationId}/read`, { method: "POST" }),

    /** 标记全部通知为已读。 */
    markAllRead: () =>
      request<void>("/notifications/read-all", { method: "POST" }),
  };
};
