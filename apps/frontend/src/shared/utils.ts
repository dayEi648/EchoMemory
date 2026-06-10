/** 共享工具函数。 */

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
