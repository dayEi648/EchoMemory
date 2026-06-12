import type { PaginatedPlaylistList, PaginatedPlaylistMembership, PlaylistDetail, PlaylistUpdateInput } from "./types";
import { createBaseApi, type ApiOptions } from "./base";
import { appendDefined } from "../utils";

export const createPlaylistApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 获取当前用户的歌单列表（分页）。 */
    listPlaylists: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedPlaylistList>(`/playlists/?${query.toString()}`);
    },

    /** 按标题搜索公开歌单（公开接口）。 */
    searchPlaylists: (params: { q?: string; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.q) query.set("q", params.q);
      return request<PaginatedPlaylistList>(`/playlists/search?${query.toString()}`, {}, false);
    },

    /** 获取指定用户的公开歌单列表（公开接口）。 */
    listPublicPlaylists: (
      userId: number,
      params: { limit?: number; offset?: number } = {},
    ) => {
      const query = new URLSearchParams();
      query.set("user_id", String(userId));
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedPlaylistList>(`/playlists/public?${query.toString()}`, {}, false);
    },

    /** 获取歌单详情（含歌曲列表）。 */
    getPlaylistDetail: (playlistId: number) =>
      request<PlaylistDetail>(`/playlists/${playlistId}`),

    /** 创建歌单。 */
    createPlaylist: (input: {
      title: string;
      description?: string;
      is_private?: boolean;
      cover_icon?: File;
    }) => {
      const formData = new FormData();
      appendDefined(formData, "title", input.title);
      appendDefined(formData, "description", input.description);
      appendDefined(formData, "is_private", input.is_private);
      appendDefined(formData, "cover_icon", input.cover_icon);
      return request<PlaylistDetail>("/playlists/", { method: "POST", body: formData });
    },

    /** 更新歌单信息。 */
    updatePlaylist: (playlistId: number, input: PlaylistUpdateInput) =>
      request<PlaylistDetail>(`/playlists/${playlistId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),

    /** 删除歌单。 */
    deletePlaylist: (playlistId: number) =>
      request<void>(`/playlists/${playlistId}`, { method: "DELETE" }),

    /** 添加歌曲到歌单。 */
    addMusicToPlaylist: (playlistId: number, musicId: number) =>
      request<PlaylistDetail>(`/playlists/${playlistId}/musics/${musicId}`, { method: "POST" }),

    /** 从歌单移除歌曲。 */
    removeMusicFromPlaylist: (playlistId: number, musicId: number) =>
      request<void>(`/playlists/${playlistId}/musics/${musicId}`, { method: "DELETE" }),

    /** 查询我的歌单及指定歌曲的归属状态（收藏弹窗用）。 */
    listPlaylistMembershipForMusic: (musicId: number) =>
      request<PaginatedPlaylistMembership>(`/playlists/membership/musics/${musicId}`),
  };
};
