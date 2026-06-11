import type { PaginatedSpacePostList, SpacePostDetail } from "./types";
import { createBaseApi, type ApiOptions } from "./base";
import { appendDefined } from "../utils";

export const createSpacePostApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 分页获取用户的说说列表。不传 user_id 则查看自己的（含私密）。 */
    listPosts: (params: { user_id?: number; limit?: number; offset?: number } = {}) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.user_id !== undefined) query.set("user_id", String(params.user_id));
      return request<PaginatedSpacePostList>(`/space-posts/?${query.toString()}`);
    },

    /** 获取单条说说详情。 */
    getPost: (postId: number) => request<SpacePostDetail>(`/space-posts/${postId}`),

    /** 创建说说（支持文字 + 多图）。 */
    createPost: (input: { content?: string; is_private?: boolean; files?: File[] }) => {
      const formData = new FormData();
      appendDefined(formData, "content", input.content);
      appendDefined(formData, "is_private", input.is_private);
      if (input.files) {
        for (const file of input.files) {
          formData.append("files", file);
        }
      }
      return request<SpacePostDetail>("/space-posts/", { method: "POST", body: formData });
    },

    /** 软删除自己的说说。 */
    deletePost: (postId: number) =>
      request<void>(`/space-posts/${postId}`, { method: "DELETE" }),

    /** 点赞说说（幂等）。 */
    likePost: (postId: number) =>
      request<void>(`/space-posts/${postId}/like`, { method: "POST" }),

    /** 取消点赞说说（幂等）。 */
    unlikePost: (postId: number) =>
      request<void>(`/space-posts/${postId}/like`, { method: "DELETE" }),
  };
};
