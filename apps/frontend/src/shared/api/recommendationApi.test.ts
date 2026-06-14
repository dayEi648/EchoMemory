import { describe, expect, it, vi } from "vitest";

import { createRecommendationApi } from "./recommendationApi";
import { createMemoryTokenStore } from "../auth/tokenStore";
import { HttpStatus } from "../constants/httpStatus";

const envelope = <T,>(data: T) => ({ code: 0, msg: "success", data });

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? HttpStatus.OK,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

const baseUrl = "http://127.0.0.1:8000/api/v1";

describe("recommendationApi", () => {
  const tokenStore = createMemoryTokenStore();

  it("requests daily recommendations with authentication", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    tokenStore.set({ accessToken: "token", refreshToken: "rt" });
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getDailyRecommendations();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/recommendations/daily"),
      expect.objectContaining({ headers: expect.any(Object) }),
    );
    const [, request] = fetchMock.mock.calls[0];
    expect(request.headers.Authorization).toBe("Bearer token");
  });

  it("requests radar recommendations with authentication", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    tokenStore.set({ accessToken: "token", refreshToken: "rt" });
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getRadarRecommendations();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/recommendations/radar"),
      expect.anything(),
    );
  });

  it("includes limit and offset in playlist query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getRecommendedPlaylists({ limit: 6, offset: 10 });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("limit=6");
    expect(url).toContain("offset=10");
  });

  it("defaults limit and offset for playlists", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getRecommendedPlaylists();

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("limit=20");
    expect(url).toContain("offset=0");
  });

  it("includes limit in albums query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getRecommendedAlbums({ limit: 6 });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("limit=6");
    expect(url).toContain("offset=0");
  });

  it("requests chart without authentication", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [] })),
    );
    tokenStore.clear();
    const api = createRecommendationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore,
    });

    await api.getRecommendationChart({ limit: 5 });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/recommendations/chart");
    expect(url).toContain("limit=5");
    const [, request] = fetchMock.mock.calls[0];
    expect(request.headers.Authorization).toBeUndefined();
  });
});
