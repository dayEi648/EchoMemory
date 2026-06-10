import type { TokenStore } from "../auth/tokenStore";
import type { AlbumDetail, AlbumListItem, AlbumCreateInput, AlbumUpdateInput, PaginatedAlbumList } from "./types";
import { createBaseApi, type ApiOptions } from "./base";
import { appendDefined } from "../utils";


export const createAlbumApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    searchAlbums: (params: { q?: string; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.q) query.set("q", params.q);
      return request<PaginatedAlbumList>(`/albums/search?${query.toString()}`, {}, false);
    },
    listAlbums: (params: { emotion_tag_id?: number; interest_tag_id?: number; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.emotion_tag_id !== undefined) query.set("emotion_tag_id", String(params.emotion_tag_id));
      if (params.interest_tag_id !== undefined) query.set("interest_tag_id", String(params.interest_tag_id));
      return request<AlbumListItem[]>(`/albums/?${query.toString()}`, {}, false);
    },
    getAlbumDetail: (albumId: number) => request<AlbumDetail>(`/albums/${albumId}`, {}, false),
    adminCreateAlbum: (input: AlbumCreateInput & { cover_icon: File; cover: File }) => {
      const formData = new FormData();
      appendDefined(formData, "title", input.title);
      appendDefined(formData, "description", input.description);
      appendDefined(formData, "source", input.source);
      appendDefined(formData, "cover_icon", input.cover_icon);
      appendDefined(formData, "cover", input.cover);
      if (input.author_ids) {
        for (const id of input.author_ids) formData.append("author_ids", String(id));
      }
      return request<AlbumDetail>("/albums/admin", { method: "POST", body: formData });
    },
    adminUpdateAlbum: (albumId: number, input: AlbumUpdateInput) =>
      request<AlbumDetail>(`/albums/admin/${albumId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
    adminDeleteAlbum: (albumId: number) => request<void>(`/albums/admin/${albumId}`, { method: "DELETE" }),
    adminAddMusicToAlbum: (albumId: number, musicId: number) =>
      request<AlbumDetail>(`/albums/admin/${albumId}/musics/${musicId}`, { method: "POST" }),
    adminRemoveMusicFromAlbum: (albumId: number, musicId: number) =>
      request<void>(`/albums/admin/${albumId}/musics/${musicId}`, { method: "DELETE" }),
  };
};
