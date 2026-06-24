import { describe, expect, it, vi } from "vitest";

import { createMemoryTokenStore } from "../auth/tokenStore";
import { createContentModerationApi } from "./contentModerationApi";

const baseUrl = "http://127.0.0.1:8000/api/v1";

describe("createContentModerationApi", () => {
  it("encodes comment moderation filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 0,
          msg: "success",
          data: { items: [], total: 0 },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = createContentModerationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await api.list("comments", {
      q: "test",
      safetyLevel: "RISKY",
      moderationStatus: "SUCCEEDED",
      isDeleted: false,
      limit: 20,
      offset: 0,
    });

    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain("/admin/content-moderation/comments?");
    expect(url).toContain("safety_level=RISKY");
    expect(url).toContain("moderation_status=SUCCEEDED");
    expect(url).toContain("is_deleted=false");
  });

  it("sends manual review and restore actions", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ code: 0, msg: "success", data: {} }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );
    const api = createContentModerationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await api.manualReview("space-posts", 7, {
      safety_score: 8,
      recommendation_score: 9,
      reason: "人工复核",
    });
    await api.restore("space-posts", 7);

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/admin/content-moderation/space-posts/7/manual-review`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/admin/content-moderation/space-posts/7/restore`,
      expect.objectContaining({ method: "POST" }),
    );
  });
});
