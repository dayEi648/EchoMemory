import type { PaginatedSystemLogs, SystemLogDetail } from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export const createLogApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    adminListLogs: (params: {
      level?: string;
      startTime?: string;
      endTime?: string;
      q?: string;
      limit?: number;
      offset?: number;
    }) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.level) query.set("level", params.level);
      if (params.startTime) query.set("start_time", params.startTime);
      if (params.endTime) query.set("end_time", params.endTime);
      if (params.q) query.set("q", params.q);
      return request<PaginatedSystemLogs>(`/admin/logs?${query.toString()}`);
    },
    adminGetLog: (logId: number) =>
      request<SystemLogDetail>(`/admin/logs/${logId}`),
  };
};
