import type { DictionaryItem, DictionaryType } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export interface DictionaryItemCreateInput {
  name: string;
}

export interface DictionaryItemUpdateInput {
  name: string;
}

export const createDictionaryApi = ({
  baseUrl,
  fetcher = fetch,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 公开：列出指定类型的字典项。 */
    listDictionary: (type: DictionaryType) =>
      request<DictionaryItem[]>(`/dictionary/${type}`, {}, false),

    /** 管理员：创建字典项。 */
    createDictionaryItem: (
      type: DictionaryType,
      data: DictionaryItemCreateInput,
    ) =>
      request<DictionaryItem>(`/dictionary/${type}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),

    /** 公开：获取单个字典项。 */
    getDictionaryItem: (type: DictionaryType, itemId: number) =>
      request<DictionaryItem>(`/dictionary/${type}/${itemId}`, {}, false),

    /** 管理员：更新字典项名称。 */
    updateDictionaryItem: (
      type: DictionaryType,
      itemId: number,
      data: DictionaryItemUpdateInput,
    ) =>
      request<DictionaryItem>(`/dictionary/${type}/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      }),

    /** 管理员：删除字典项（仅当未被引用时）。 */
    deleteDictionaryItem: (type: DictionaryType, itemId: number) =>
      request<void>(`/dictionary/${type}/${itemId}`, {
        method: "DELETE",
      }),
  };
};
