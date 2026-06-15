import type { CommentItem, CommentCreateInput, PaginatedCommentList } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createCommentApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  /** 获取根评论列表（公开接口）。 */
  const listRootComments = (
    targetType: string,
    targetId: number,
    params: { limit?: number; offset?: number; sort_by?: string } = {},
  ) => {
    const query = new URLSearchParams();
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    if (params.sort_by) query.set("sort_by", params.sort_by);
    return request<PaginatedCommentList>(
      `/comments/${targetType}/${targetId}?${query.toString()}`,
      {},
      false,
    );
  };

  /** 获取某条评论的所有回复（公开接口）。 */
  const listReplies = (rootId: number) =>
    request<PaginatedCommentList>(`/comments/replies/${rootId}`, {}, false);

  return {
    listRootComments,
    listReplies,

    /** 发表评论或回复。 */
    createComment: (input: CommentCreateInput) =>
      request<CommentItem>("/comments/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),

    /** 删除自己的评论。 */
    deleteComment: (commentId: number) =>
      request<void>(`/comments/${commentId}`, { method: "DELETE" }),

    /** 点赞评论（幂等）。 */
    likeComment: (commentId: number) =>
      request<void>(`/comments/${commentId}/like`, { method: "POST" }),

    /** 取消点赞。 */
    unlikeComment: (commentId: number) =>
      request<void>(`/comments/${commentId}/like`, { method: "DELETE" }),

    /** 点踩评论（幂等）。 */
    dislikeComment: (commentId: number) =>
      request<void>(`/comments/${commentId}/dislike`, { method: "POST" }),

    /** 取消点踩。 */
    undislikeComment: (commentId: number) =>
      request<void>(`/comments/${commentId}/dislike`, { method: "DELETE" }),
  };
};
