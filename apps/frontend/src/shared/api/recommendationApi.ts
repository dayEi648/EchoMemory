import type {
  PaginatedAlbumList,
  PaginatedMusicList,
  PaginatedPlaylistList,
  RecommendChartList,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createRecommendationApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 获取当前用户的每日推荐。 */
    getDailyRecommendations: () => {
      return request<PaginatedMusicList>("/recommendations/daily");
    },

    /** 获取当前用户的私人雷达。 */
    getRadarRecommendations: () => {
      return request<PaginatedMusicList>("/recommendations/radar");
    },

    /** 根据用户口味推荐公开歌单。 */
    getRecommendedPlaylists: (params: {
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedPlaylistList>(
        `/recommendations/playlists?${query.toString()}`,
      );
    },

    /** 根据用户口味推荐专辑。 */
    getRecommendedAlbums: (params: {
      limit?: number;
      offset?: number;
    } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      return request<PaginatedAlbumList>(
        `/recommendations/albums?${query.toString()}`,
      );
    },

    /** 获取今日推荐榜。 */
    getRecommendationChart: (params: { limit?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      return request<RecommendChartList>(
        `/recommendations/chart?${query.toString()}`,
        {},
        false,
      );
    },
  };
};
