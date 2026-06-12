/**
 * 集中管理 API 实例与 tokenStore。
 * 所有页面和 store 应从此文件获取 API，避免分散创建导致测试注入失效。
 */
import { createLocalStorageTokenStore, type TokenStore } from "../auth/tokenStore";
import { createMusicApi } from "./musicApi";
import { createAlbumApi } from "./albumApi";
import { createPlaylistApi } from "./playlistApi";
import { createPlayHistoryApi } from "./playHistoryApi";
import { createCollectionApi } from "./collectionApi";
import { createCommentApi } from "./commentApi";
import { createSpacePostApi } from "./spacePostApi";
import { createDictionaryApi } from "./dictionaryApi";
import { createUserApi } from "./userApi";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export type ApiRegistry = {
  userApi: ReturnType<typeof createUserApi>;
  musicApi: ReturnType<typeof createMusicApi>;
  albumApi: ReturnType<typeof createAlbumApi>;
  playlistApi: ReturnType<typeof createPlaylistApi>;
  playHistoryApi: ReturnType<typeof createPlayHistoryApi>;
  collectionApi: ReturnType<typeof createCollectionApi>;
  commentApi: ReturnType<typeof createCommentApi>;
  spacePostApi: ReturnType<typeof createSpacePostApi>;
  dictionaryApi: ReturnType<typeof createDictionaryApi>;
};

function buildApis(tokenStore: TokenStore): ApiRegistry {
  const options = { baseUrl: BASE_URL, tokenStore };
  return {
    userApi: createUserApi(options),
    musicApi: createMusicApi(options),
    albumApi: createAlbumApi(options),
    playlistApi: createPlaylistApi(options),
    playHistoryApi: createPlayHistoryApi(options),
    collectionApi: createCollectionApi(options),
    commentApi: createCommentApi(options),
    spacePostApi: createSpacePostApi(options),
    dictionaryApi: createDictionaryApi(options),
  };
}

let currentTokenStore = createLocalStorageTokenStore();
let apis = buildApis(currentTokenStore);

/** 获取当前 API 注册表（共享同一 tokenStore）。 */
export function getApis(): ApiRegistry {
  return apis;
}

/** 替换 tokenStore 并重建所有 API 实例（测试与内部初始化共用）。 */
export function replaceApiTokenStore(tokenStore: TokenStore): void {
  currentTokenStore = tokenStore;
  apis = buildApis(tokenStore);
  userApi = apis.userApi;
  musicApi = apis.musicApi;
  albumApi = apis.albumApi;
  playlistApi = apis.playlistApi;
  playHistoryApi = apis.playHistoryApi;
  collectionApi = apis.collectionApi;
  commentApi = apis.commentApi;
  spacePostApi = apis.spacePostApi;
  dictionaryApi = apis.dictionaryApi;
}

export let userApi = apis.userApi;
export let musicApi = apis.musicApi;
export let albumApi = apis.albumApi;
export let playlistApi = apis.playlistApi;
export let playHistoryApi = apis.playHistoryApi;
export let collectionApi = apis.collectionApi;
export let commentApi = apis.commentApi;
export let spacePostApi = apis.spacePostApi;
export let dictionaryApi = apis.dictionaryApi;
