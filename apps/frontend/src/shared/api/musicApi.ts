import type { TokenStore } from "../auth/tokenStore";
import type { MusicDetail, MusicListItem, MusicUpdateInput, PaginatedAdminMusicList, PaginatedMusicList } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

const appendDefined = (formData: FormData, key: string, value: unknown) => {
  if (value === undefined || value === null || value === "") {
    return;
  }
  if (value instanceof File) {
    formData.append(key, value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      formData.append(key, String(item));
    }
    return;
  }
  formData.append(key, String(value));
};

export const createMusicApi = ({ baseUrl, fetcher = fetch, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    searchMusic: (params: { q?: string; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.q) query.set("q", params.q);
      return request<PaginatedMusicList>(`/music/search?${query.toString()}`, {}, false);
    },
    listMusic: (params: { style_id?: number; language_id?: number; is_vip?: boolean; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.style_id !== undefined) query.set("style_id", String(params.style_id));
      if (params.language_id !== undefined) query.set("language_id", String(params.language_id));
      if (params.is_vip !== undefined) query.set("is_vip", String(params.is_vip));
      return request<MusicListItem[]>(`/music/?${query.toString()}`, {}, false);
    },
    getMusicDetail: (musicId: number) => request<MusicDetail>(`/music/${musicId}`, {}, false),
    adminImportMusic: (input: {
      title: string;
      audio_file: File;
      cover_icon: File;
      is_vip?: boolean;
      source?: string;
      style_id?: number;
      language_id?: number;
      release_date?: string;
      author_ids?: number[];
      instrument_ids?: number[];
      emotion_tag_ids?: number[];
      interest_tag_ids?: number[];
      cover_home?: File;
      cover_play?: File;
      lyrics_file?: File;
    }) => {
      const formData = new FormData();
      appendDefined(formData, "title", input.title);
      appendDefined(formData, "audio_file", input.audio_file);
      appendDefined(formData, "cover_icon", input.cover_icon);
      appendDefined(formData, "is_vip", input.is_vip);
      appendDefined(formData, "source", input.source);
      appendDefined(formData, "style_id", input.style_id);
      appendDefined(formData, "language_id", input.language_id);
      appendDefined(formData, "release_date", input.release_date);
      if (input.author_ids) {
        for (const id of input.author_ids) formData.append("author_ids", String(id));
      }
      if (input.instrument_ids) {
        for (const id of input.instrument_ids) formData.append("instrument_ids", String(id));
      }
      if (input.emotion_tag_ids) {
        for (const id of input.emotion_tag_ids) formData.append("emotion_tag_ids", String(id));
      }
      if (input.interest_tag_ids) {
        for (const id of input.interest_tag_ids) formData.append("interest_tag_ids", String(id));
      }
      appendDefined(formData, "cover_home", input.cover_home);
      appendDefined(formData, "cover_play", input.cover_play);
      appendDefined(formData, "lyrics_file", input.lyrics_file);
      return request<MusicDetail>("/music/admin/import", { method: "POST", body: formData });
    },
    adminUpdateMusic: (musicId: number, input: MusicUpdateInput) =>
      request<MusicDetail>(`/music/admin/${musicId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
    adminListMusic: (params: {
      q?: string;
      style_id?: number;
      language_id?: number;
      is_vip?: boolean;
      is_published?: boolean;
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.q) query.set("q", params.q);
      if (params.style_id !== undefined) query.set("style_id", String(params.style_id));
      if (params.language_id !== undefined) query.set("language_id", String(params.language_id));
      if (params.is_vip !== undefined) query.set("is_vip", String(params.is_vip));
      if (params.is_published !== undefined) query.set("is_published", String(params.is_published));
      return request<PaginatedAdminMusicList>(`/music/admin/list?${query.toString()}`);
    },
    adminGetMusicDetail: (musicId: number) => request<MusicDetail>(`/music/admin/${musicId}`),
    adminPublishMusic: (musicId: number) => request<MusicDetail>(`/music/admin/${musicId}/publish`, { method: "POST" }),
    adminUnpublishMusic: (musicId: number) => request<MusicDetail>(`/music/admin/${musicId}/unpublish`, { method: "POST" }),
  };
};
