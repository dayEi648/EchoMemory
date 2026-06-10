import type { DictionaryItem, DictionaryType } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createDictionaryApi = ({ baseUrl, fetcher = fetch, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    listDictionary: (type: DictionaryType) => request<DictionaryItem[]>(`/dictionary/${type}`, {}, false),
  };
};
