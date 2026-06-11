/** 共享工具函数。 */

import type { AlbumMusicItem, Author, MusicDetail, MusicListItem } from "./api/types";
import type { PlayerTrack } from "./stores/playerStore";

/**
 * 将非空值追加到 FormData。
 *
 * 对 undefined、null、空字符串跳过；
 * File 直接追加；数组展开为多个同名字段；
 * 其他类型转为字符串追加。
 */
export const appendDefined = (formData: FormData, key: string, value: unknown): void => {
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

/**
 * 将秒数格式化为 mm:ss 字符串。
 *
 * @param seconds 秒数，非有限值或负数时返回 "0:00"。
 */
export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

/**
 * 将作者列表格式化为可展示文本。
 *
 * @param authors 后端返回的作者列表；缺失或为空时使用 fallback。
 * @param fallback 没有作者信息时展示的文本。
 */
export function formatAuthors(authors: Author[] | null | undefined, fallback = "未知艺人"): string {
  if (!Array.isArray(authors)) {
    return fallback;
  }
  const names = authors
    .map((author) => author.nickname || author.username)
    .filter((name): name is string => Boolean(name));
  return names.join(", ") || fallback;
}

/**
 * 将音乐详情转换为播放器曲目。
 *
 * @param detail 音乐详情接口返回值。
 * @returns 播放器可消费的曲目对象。
 */
/**
 * 将 ISO 日期字符串格式化为相对时间（如"3 分钟前"、""2 小时前"、""3 天前"），
 * 超过 7 天则返回 YYYY-MM-DD 格式。
 */
export function formatRelativeTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function toPlayerTrack(detail: MusicDetail): PlayerTrack {
  return {
    id: detail.id,
    title: detail.title,
    is_vip: detail.is_vip,
    hot: detail.hot,
    play_count: detail.play_count,
    cover_icon_url: detail.cover_icon_url,
    authors: detail.authors,
    style: detail.style ?? undefined,
    language: detail.language ?? undefined,
    emotion_tags: detail.emotion_tags,
    interest_tags: detail.interest_tags,
    albums: [],
    created_at: detail.created_at,
    file_url: detail.file_url,
  };
}

/** 将音乐列表项转换为播放器曲目。 */
export function toPlayerTrackFromListItem(
  item: MusicListItem,
  fileUrl: string | null,
): PlayerTrack {
  return {
    ...item,
    emotion_tags: item.emotion_tags ?? [],
    interest_tags: item.interest_tags ?? [],
    albums: item.albums ?? [],
    file_url: fileUrl,
  };
}

/** 将专辑内嵌歌曲转换为播放器曲目。 */
export function toPlayerTrackFromAlbumMusic(
  item: AlbumMusicItem,
  authors: Author[],
  fileUrl: string | null,
  createdAt: string,
): PlayerTrack {
  return {
    id: item.id,
    title: item.title,
    is_vip: item.is_vip,
    hot: item.hot,
    play_count: item.play_count,
    cover_icon_url: item.cover_icon_url,
    authors,
    emotion_tags: [],
    interest_tags: [],
    albums: [],
    created_at: createdAt,
    file_url: fileUrl,
  };
}
