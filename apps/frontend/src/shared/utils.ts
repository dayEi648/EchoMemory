/** 共享工具函数。 */

import type { Author, MusicDetail } from "./api/types";
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
