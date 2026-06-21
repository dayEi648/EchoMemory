import { describe, expect, it, vi } from "vitest";

import { createMemoryTokenStore } from "../auth/tokenStore";
import { createAgentMonitorApi } from "./agentMonitorApi";

const baseUrl = "http://127.0.0.1:8000/api/v1";

describe("createAgentMonitorApi", () => {
  it("encodes run filters and cursor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 0,
          msg: "success",
          data: { items: [], total: 0, next_cursor: null },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = createAgentMonitorApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await api.listRuns({
      scenario: "ai_conversation",
      userId: 42,
      status: "FAILED",
      model: "deepseek-v4-flash",
      startTime: "2026-06-21T00:00",
      endTime: "2026-06-22T00:00",
      q: "conversation",
      cursor: "next-page",
      limit: 20,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/admin/agent-monitor/runs?scenario=ai_conversation&user_id=42&status=FAILED",
      ),
      expect.anything(),
    );
    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).toContain("cursor=next-page");
    expect(requestedUrl).toContain("model=deepseek-v4-flash");
  });

  it("loads run detail and events independently", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 0,
            msg: "success",
            data: { id: "run-1", scenario: "ai_conversation" },
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ code: 0, msg: "success", data: [] }),
          { headers: { "Content-Type": "application/json" } },
        ),
      );
    const api = createAgentMonitorApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await Promise.all([api.getRun("run-1"), api.listEvents("run-1")]);

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/admin/agent-monitor/runs/run-1`,
      expect.anything(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/admin/agent-monitor/runs/run-1/events`,
      expect.anything(),
    );
  });
});
