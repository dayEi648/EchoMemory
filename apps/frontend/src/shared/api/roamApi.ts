import { createBaseApi, type ApiOptions } from "./base";
import type { RoamState, RoamReport, RoamGuideResponse } from "./types";

export const createRoamApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 开始新的私人漫游。 */
    start: () => request<RoamState>("/roam/start", { method: "POST" }),

    /** 获取当前漫游状态。 */
    getState: () => request<RoamState>("/roam/state"),

    /** 下一首（生成或导航）。 */
    next: () => request<RoamState>("/roam/next", { method: "POST" }),

    /** 上一首。 */
    prev: () => request<RoamState>("/roam/prev", { method: "POST" }),

    /** 收藏歌曲到指定歌单。不传 playlistId 则默认"我喜欢的音乐"。 */
    favorite: (songId: number, playlistId?: number) =>
      request<{ success: boolean }>(`/roam/${songId}/favorite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playlist_id: playlistId ?? null }),
      }),

    /** 不喜欢歌曲。 */
    dislike: (songId: number, reasons?: Record<string, unknown>) =>
      request<{ success: boolean }>(`/roam/${songId}/dislike`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: reasons ? JSON.stringify(reasons) : undefined,
      }),

    /** 自然语言引导方向。 */
    guide: (hint: string) =>
      request<RoamGuideResponse>("/roam/guide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hint }),
      }),

    /** 结束漫游并获取报告。 */
    end: () => request<RoamReport>("/roam/end", { method: "POST" }),
  };
};
