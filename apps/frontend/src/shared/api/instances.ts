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
import { createCarouselApi } from "./carouselApi";
import { createLogApi } from "./logApi";
import { createUserApi } from "./userApi";
import { createNotificationApi } from "./notificationApi";
import { createMessageApi } from "./messageApi";
import { createRecommendationApi } from "./recommendationApi";
import { createAIConversationApi } from "./aiConversationApi";

const isDev = import.meta.env.DEV;
const envBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;

if (!isDev && !envBaseUrl) {
  throw new Error(
    "生产环境必须配置 VITE_API_BASE_URL。" +
    "请在 apps/frontend/.env.production 中设置后端 API 地址，" +
    "例如：VITE_API_BASE_URL=https://api.echomemory.com/api/v1",
  );
}

export const API_BASE_URL: string = envBaseUrl ?? "/api/v1";

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
  carouselApi: ReturnType<typeof createCarouselApi>;
  notificationApi: ReturnType<typeof createNotificationApi>;
  messageApi: ReturnType<typeof createMessageApi>;
  recommendationApi: ReturnType<typeof createRecommendationApi>;
  aiConversationApi: ReturnType<typeof createAIConversationApi>;
  logApi: ReturnType<typeof createLogApi>;
};

function buildApis(tokenStore: TokenStore): ApiRegistry {
  const options = { baseUrl: API_BASE_URL, tokenStore };
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
    carouselApi: createCarouselApi(options),
    notificationApi: createNotificationApi(options),
    messageApi: createMessageApi(options),
    recommendationApi: createRecommendationApi(options),
    aiConversationApi: createAIConversationApi(options),
    logApi: createLogApi(options),
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
  carouselApi = apis.carouselApi;
  notificationApi = apis.notificationApi;
  messageApi = apis.messageApi;
  recommendationApi = apis.recommendationApi;
  aiConversationApi = apis.aiConversationApi;
  logApi = apis.logApi;
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
export let carouselApi = apis.carouselApi;
export let notificationApi = apis.notificationApi;
export let messageApi = apis.messageApi;
export let recommendationApi = apis.recommendationApi;
export let aiConversationApi = apis.aiConversationApi;
export let logApi = apis.logApi;
