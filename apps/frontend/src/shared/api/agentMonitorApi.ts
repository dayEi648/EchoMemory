import type {
  AgentMonitorEvent,
  AgentMonitorRunDetail,
  AgentMonitorRunPage,
} from "./types";
import { createBaseApi, type ApiOptions } from "./base";

export type AgentMonitorRunFilters = {
  scenario?: string;
  userId?: number;
  status?: string;
  model?: string;
  startTime?: string;
  endTime?: string;
  q?: string;
  cursor?: string;
  limit?: number;
};

export const createAgentMonitorApi = ({
  baseUrl,
  fetcher,
  tokenStore,
}: ApiOptions) => {
  const { request } = createBaseApi({ baseUrl, fetcher, tokenStore });

  return {
    listRuns: (filters: AgentMonitorRunFilters) => {
      const query = new URLSearchParams();
      if (filters.scenario) query.set("scenario", filters.scenario);
      if (filters.userId !== undefined) {
        query.set("user_id", String(filters.userId));
      }
      if (filters.status) query.set("status", filters.status);
      if (filters.model) query.set("model", filters.model);
      if (filters.startTime) query.set("start_time", filters.startTime);
      if (filters.endTime) query.set("end_time", filters.endTime);
      if (filters.q) query.set("q", filters.q);
      if (filters.cursor) query.set("cursor", filters.cursor);
      query.set("limit", String(filters.limit ?? 20));
      return request<AgentMonitorRunPage>(
        `/admin/agent-monitor/runs?${query.toString()}`,
      );
    },
    getRun: (runId: string) =>
      request<AgentMonitorRunDetail>(
        `/admin/agent-monitor/runs/${encodeURIComponent(runId)}`,
      ),
    listEvents: (runId: string) =>
      request<AgentMonitorEvent[]>(
        `/admin/agent-monitor/runs/${encodeURIComponent(runId)}/events`,
      ),
  };
};

