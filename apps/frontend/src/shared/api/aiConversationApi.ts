import type {
  AIConversation,
  AIConversationCreateInput,
  AIConversationMessage,
  AIConversationMessageCreateInput,
  AIConversationMessages,
  AIConversationWithFirstMessage,
  AIStreamChunk,
  PaginatedAIConversationList,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createAIConversationApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  const buildPath = (path: string) => `${baseUrl}/ai/conversations${path}`;

  const getAuthHeader = (): Record<string, string> => {
    const tokens = tokenStore.get();
    return tokens ? { Authorization: `Bearer ${tokens.accessToken}` } : {};
  };

  return {
    /** 分页获取当前用户的 AI 会话列表。 */
    listConversations: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 30));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedAIConversationList>(
        `/ai/conversations?${query.toString()}`,
      );
    },

    /** 创建新的 AI 会话。 */
    createConversation: (input: AIConversationCreateInput = {}) =>
      request<AIConversationWithFirstMessage>("/ai/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),

    /** 获取指定会话的消息列表。 */
    getMessages: (conversationId: number) =>
      request<AIConversationMessages>(
        `/ai/conversations/${conversationId}/messages`,
      ),

    /** 非流式发送消息。 */
    sendMessage: (
      conversationId: number,
      input: AIConversationMessageCreateInput,
    ) =>
      request<AIConversationMessage>(
        `/ai/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        },
      ),

    /** 创建会话并流式发送首条消息，返回 SSE chunk 异步迭代器。 */
    streamFirstMessage: async function* (
      content: string,
      input: Omit<AIConversationCreateInput, "first_message" | "stream"> = {},
    ): AsyncGenerator<AIStreamChunk> {
      const response = await (fetcher ?? globalThis.fetch)(buildPath(""), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          ...getAuthHeader(),
        },
        body: JSON.stringify({ ...input, first_message: content, stream: true }),
      });

      if (!response.ok) {
        const text = await response.text().catch(() => "请求失败");
        throw new Error(text);
      }

      const body = response.body;
      if (!body) {
        throw new Error("响应体为空");
      }

      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const chunk = parseSSELine(line);
            if (chunk) {
              yield chunk;
              if (chunk.type === "done" || chunk.type === "error") {
                return;
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    },

    /** 流式发送消息，返回 SSE chunk 异步迭代器。 */
    streamMessage: async function* (
      conversationId: number,
      content: string,
    ): AsyncGenerator<AIStreamChunk> {
      const response = await (fetcher ?? globalThis.fetch)(
        buildPath(`/${conversationId}/messages`),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...getAuthHeader(),
          },
          body: JSON.stringify({ content, stream: true }),
        },
      );

      if (!response.ok) {
        const text = await response.text().catch(() => "请求失败");
        throw new Error(text);
      }

      const body = response.body;
      if (!body) {
        throw new Error("响应体为空");
      }

      const reader = body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const chunk = parseSSELine(line);
            if (chunk) {
              yield chunk;
              if (chunk.type === "done" || chunk.type === "error") {
                return;
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    },

    /** 手动更新会话标题。 */
    updateTitle: (conversationId: number, title: string) =>
      request<AIConversation>(`/ai/conversations/${conversationId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      }),

    /** 软删除指定会话。 */
    deleteConversation: (conversationId: number) =>
      request<void>(`/ai/conversations/${conversationId}`, {
        method: "DELETE",
      }),
  };
};

/** 解析单行 SSE 数据。 */
export function parseSSELine(line: string): AIStreamChunk | null {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith(":")) {
    return null;
  }

  const prefix = "data: ";
  if (!trimmed.startsWith(prefix)) {
    return null;
  }

  const payload = trimmed.slice(prefix.length);
  if (payload === "[DONE]") {
    return { type: "done", data: "", model: null };
  }

  try {
    const parsed = JSON.parse(payload) as AIStreamChunk;
    if (
      parsed &&
      typeof parsed === "object" &&
      ["content", "reasoning", "done", "error"].includes(parsed.type)
    ) {
      return parsed;
    }
  } catch {
    // 非 JSON 行忽略
  }

  return null;
}
