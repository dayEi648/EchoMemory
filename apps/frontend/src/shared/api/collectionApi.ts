import type {
  AlbumCollectionItem,
  PlaylistCollectionItem,
  PaginatedMusicCollection,
  PaginatedAlbumCollection,
  PaginatedPlaylistCollection,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createCollectionApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /* ---------- 音乐收藏（派生自歌单归属；通过歌单选择器加入） ---------- */

    /** 取消收藏音乐：从全部歌单移除（幂等）。 */
    uncollectMusic: (musicId: number) =>
      request<void>(`/collections/musics/${musicId}`, { method: "DELETE" }),

    /** 分页获取收藏音乐列表。 */
    listMusicCollections: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedMusicCollection>(`/collections/musics?${query.toString()}`);
    },

    /* ---------- 专辑收藏 ---------- */

    /** 收藏专辑（幂等）。 */
    collectAlbum: (albumId: number) =>
      request<AlbumCollectionItem>(`/collections/albums/${albumId}`, { method: "POST" }),

    /** 取消收藏专辑（幂等）。 */
    uncollectAlbum: (albumId: number) =>
      request<void>(`/collections/albums/${albumId}`, { method: "DELETE" }),

    /** 分页获取收藏专辑列表。 */
    listAlbumCollections: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedAlbumCollection>(`/collections/albums?${query.toString()}`);
    },

    /* ---------- 歌单收藏 ---------- */

    /** 收藏歌单（幂等）。 */
    collectPlaylist: (playlistId: number) =>
      request<PlaylistCollectionItem>(`/collections/playlists/${playlistId}`, { method: "POST" }),

    /** 取消收藏歌单（幂等）。 */
    uncollectPlaylist: (playlistId: number) =>
      request<void>(`/collections/playlists/${playlistId}`, { method: "DELETE" }),

    /** 分页获取收藏歌单列表。 */
    listPlaylistCollections: (params: { limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedPlaylistCollection>(`/collections/playlists?${query.toString()}`);
    },
  };
};
