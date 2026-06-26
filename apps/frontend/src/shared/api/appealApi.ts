import type { AppealCreateInput, ContentAppeal } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createAppealApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    /** 用户发起申诉 */
    create: (input: AppealCreateInput) =>
      request<ContentAppeal>("/moderation/appeals/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
    /** 管理员列出申诉 */
    adminList: (params?: { status?: string; limit?: number; offset?: number }) => {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      query.set("limit", String(params?.limit ?? 20));
      query.set("offset", String(params?.offset ?? 0));
      return request<{ items: ContentAppeal[]; total: number }>(
        `/moderation/appeals/admin?${query.toString()}`,
      );
    },
    /** 管理员批准 */
    adminApprove: (appealId: number, adminNote?: string | null) =>
      request<ContentAppeal>(
        `/moderation/appeals/admin/${appealId}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ admin_note: adminNote ?? null }),
        },
      ),
    /** 管理员驳回 */
    adminDeny: (appealId: number, adminNote?: string | null) =>
      request<ContentAppeal>(
        `/moderation/appeals/admin/${appealId}/deny`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ admin_note: adminNote ?? null }),
        },
      ),
  };
};
