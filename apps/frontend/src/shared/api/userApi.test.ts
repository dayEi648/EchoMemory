import { beforeEach, describe, expect, it, vi } from "vitest";

import { createUserApi } from "./userApi";
import { createMemoryTokenStore } from "../auth/tokenStore";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

describe("userApi", () => {
  const baseUrl = "http://127.0.0.1:8000/api/v1";

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("stores both access token and refresh token after login", async () => {
    const tokenStore = createMemoryTokenStore();
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "access-token",
        refresh_token: "refresh-token",
        token_type: "bearer",
      }),
    );

    const api = createUserApi({ baseUrl, fetcher: fetchMock, tokenStore });
    await api.login({ username: "alice", password: "secret123" });

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/auth/login`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "alice", password: "secret123" }),
      }),
    );
    expect(tokenStore.get()).toEqual({
      accessToken: "access-token",
      refreshToken: "refresh-token",
    });
  });

  it("sends city as a string field when registering", async () => {
    const tokenStore = createMemoryTokenStore();
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        access_token: "access-token",
        refresh_token: "refresh-token",
        token_type: "bearer",
      }),
    );

    const api = createUserApi({ baseUrl, fetcher: fetchMock, tokenStore });
    await api.register({
      username: "alice",
      nickname: "Alice",
      password: "secret123",
      gender: 1,
      city: "杭州",
    });

    const [, request] = fetchMock.mock.calls[0];
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("city")).toBe("杭州");
    expect((request.body as FormData).has("city_id")).toBe(false);
  });

  it("refreshes once on 401 and clears session when refresh fails", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "expired", refreshToken: "refresh" });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid" }, { status: 401 }));

    const api = createUserApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await expect(api.getMe()).rejects.toThrow("invalid");
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${baseUrl}/auth/refresh`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(tokenStore.get()).toBeNull();
  });

  it("sends profile city updates as city, not city_id", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access-token", refreshToken: "refresh-token" });
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 1,
        username: "alice",
        nickname: "Alice",
        gender: 1,
        role: 0,
        level: 0,
        exp: 0,
        city: "成都",
        is_verified: false,
        like_count: 0,
        status: 0,
        safety_score: 10,
      }),
    );

    const api = createUserApi({ baseUrl, fetcher: fetchMock, tokenStore });
    await api.updateMe({ nickname: "Alice", city: "成都" });

    const [, request] = fetchMock.mock.calls[0];
    expect(request.headers).toEqual(
      expect.objectContaining({ Authorization: "Bearer access-token" }),
    );
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("city")).toBe("成都");
    expect((request.body as FormData).has("city_id")).toBe(false);
  });
});
