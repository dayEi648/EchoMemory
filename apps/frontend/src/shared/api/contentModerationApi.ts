import type {
  AdminModeratedContent,
  ManualModerationInput,
  PaginatedModeratedContent,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export type ModerationResource = "comments" | "space-posts";

export type ContentModerationFilters = {
  q?: string;
  userId?: number;
  targetType?: string;
  targetId?: number;
  safetyLevel?: string;
  recommendationLevel?: string;
  moderationStatus?: string;
  isDeleted?: boolean;
  isRecommended?: boolean;
  startTime?: string;
  endTime?: string;
  limit?: number;
  offset?: number;
};

export const createContentModerationApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  const itemPath = (
    resource: ModerationResource,
    contentId: number,
    action: string,
  ) =>
    `/admin/content-moderation/${resource}/${contentId}/${action}`;

  return {
    list: (
      resource: ModerationResource,
      filters: ContentModerationFilters = {},
    ) => {
      const query = new URLSearchParams();
      if (filters.q) query.set("q", filters.q);
      if (filters.userId !== undefined) {
        query.set("user_id", String(filters.userId));
      }
      if (filters.targetType) query.set("target_type", filters.targetType);
      if (filters.targetId !== undefined) {
        query.set("target_id", String(filters.targetId));
      }
      if (filters.safetyLevel) {
        query.set("safety_level", filters.safetyLevel);
      }
      if (filters.recommendationLevel) {
        query.set("recommendation_level", filters.recommendationLevel);
      }
      if (filters.moderationStatus) {
        query.set("moderation_status", filters.moderationStatus);
      }
      if (filters.isDeleted !== undefined) {
        query.set("is_deleted", String(filters.isDeleted));
      }
      if (filters.isRecommended !== undefined) {
        query.set("is_recommended", String(filters.isRecommended));
      }
      if (filters.startTime) query.set("start_time", filters.startTime);
      if (filters.endTime) query.set("end_time", filters.endTime);
      query.set("limit", String(filters.limit ?? 20));
      query.set("offset", String(filters.offset ?? 0));
      return request<PaginatedModeratedContent>(
        `/admin/content-moderation/${resource}?${query.toString()}`,
      );
    },
    rereview: (resource: ModerationResource, contentId: number) =>
      request<AdminModeratedContent>(
        itemPath(resource, contentId, "rereview"),
        { method: "POST" },
      ),
    manualReview: (
      resource: ModerationResource,
      contentId: number,
      input: ManualModerationInput,
    ) =>
      request<AdminModeratedContent>(
        itemPath(resource, contentId, "manual-review"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        },
      ),
    restore: (resource: ModerationResource, contentId: number) =>
      request<AdminModeratedContent>(
        itemPath(resource, contentId, "restore"),
        { method: "POST" },
      ),
  };
};
