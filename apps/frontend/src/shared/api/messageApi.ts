import type {
  ConversationItem,
  DirectMessageItem,
  PaginatedConversationList,
  PaginatedDirectMessageList,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createMessageApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 分页获取当前用户的会话列表。 */
    listConversations: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 30));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedConversationList>(
        `/messages/conversations?${query.toString()}`,
      );
    },

    /** 获取与指定用户的会话元数据，会话不存在返回 404。 */
    getConversationWithUser: (userId: number) =>
      request<ConversationItem>(`/messages/conversations/with/${userId}`),

    /** 分页拉取会话内消息（按时间倒序）。 */
    listMessages: (
      conversationId: number,
      params: { limit?: number; offset?: number } = {},
    ) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 30));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedDirectMessageList>(
        `/messages/conversations/${conversationId}/messages?${query.toString()}`,
      );
    },

    /** 标记会话已读（清零未读数）。 */
    markRead: (conversationId: number) =>
      request<void>(`/messages/conversations/${conversationId}/read`, {
        method: "POST",
      }),

    /** 向指定用户发送私信。 */
    sendMessage: (userId: number, content: string) =>
      request<DirectMessageItem>(`/messages/${userId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      }),

    /** 屏蔽用户（幂等）。 */
    blockUser: (userId: number) =>
      request<void>(`/users/${userId}/block`, { method: "POST" }),

    /** 取消屏蔽（幂等）。 */
    unblockUser: (userId: number) =>
      request<void>(`/users/${userId}/block`, { method: "DELETE" }),
  };
};
