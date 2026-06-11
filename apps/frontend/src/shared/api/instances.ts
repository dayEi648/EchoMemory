/**
 * 预配置的 API 实例，集中管理 base URL 和 token store。
 * 所有页面和组件应从此文件导入，而非各自创建重复的实例。
 */
import { createLocalStorageTokenStore } from "../auth/tokenStore";
import { createMusicApi } from "./musicApi";
import { createAlbumApi } from "./albumApi";
import { createPlaylistApi } from "./playlistApi";
import { createPlayHistoryApi } from "./playHistoryApi";
import { createCollectionApi } from "./collectionApi";
import { createCommentApi } from "./commentApi";
import { createSpacePostApi } from "./spacePostApi";
import { createDictionaryApi } from "./dictionaryApi";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();

export const musicApi = createMusicApi({ baseUrl: BASE_URL, tokenStore });
export const albumApi = createAlbumApi({ baseUrl: BASE_URL, tokenStore });
export const playlistApi = createPlaylistApi({ baseUrl: BASE_URL, tokenStore });
export const playHistoryApi = createPlayHistoryApi({ baseUrl: BASE_URL, tokenStore });
export const collectionApi = createCollectionApi({ baseUrl: BASE_URL, tokenStore });
export const commentApi = createCommentApi({ baseUrl: BASE_URL, tokenStore });
export const spacePostApi = createSpacePostApi({ baseUrl: BASE_URL, tokenStore });
export const dictionaryApi = createDictionaryApi({ baseUrl: BASE_URL, tokenStore });
