import { describe, expect, it, vi } from "vitest";

import { ApiError, createBaseApi } from "./base";
import { createMemoryTokenStore } from "../auth/tokenStore";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

describe("createBaseApi parseResponse", () => {
  const baseUrl = "http://127.0.0.1:8000/api/v1";

  it("creates ApiError instances compatible with instanceof", () => {
    const error = new ApiError("bad", 400);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.name).toBe("ApiError");
  });

  it("extracts detail from object error bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: "用户名已存在" }, { status: 409 }));
    const { request } = createBaseApi({ baseUrl, fetcher: fetchMock, tokenStore: createMemoryTokenStore() });

    await expect(request("/users/1")).rejects.toMatchObject({
      message: "用户名已存在",
      status: 409,
    });
  });

  it("falls back when error body is null", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(null, { status: 500 }));
    const { request } = createBaseApi({ baseUrl, fetcher: fetchMock, tokenStore: createMemoryTokenStore() });

    await expect(request("/users/1")).rejects.toMatchObject({
      message: "请求失败",
      status: 500,
    });
  });

  it("returns undefined for 204 responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const { request } = createBaseApi({ baseUrl, fetcher: fetchMock, tokenStore: createMemoryTokenStore() });

    await expect(request("/noop")).resolves.toBeUndefined();
  });
});
