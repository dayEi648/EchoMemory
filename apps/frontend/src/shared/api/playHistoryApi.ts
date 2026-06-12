import type { PaginatedPlayHistoryList, PlayHistoryItem } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createPlayHistoryApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    recordPlay: (musicId: number, playlistId?: number) =>
      request<PlayHistoryItem>("/play-history/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          playlistId != null
            ? { music_id: musicId, playlist_id: playlistId }
            : { music_id: musicId },
        ),
      }),
    listPlayHistory: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedPlayHistoryList>(`/play-history/?${query.toString()}`);
    },
    deletePlayHistory: (historyId: number) => request<void>(`/play-history/${historyId}`, { method: "DELETE" }),
    clearPlayHistory: () => request<void>("/play-history/", { method: "DELETE" }),
  };
};
