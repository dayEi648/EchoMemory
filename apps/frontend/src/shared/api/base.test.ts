import { describe, expect, it, vi } from "vitest";

import { ApiError, createBaseApi } from "./base";
import { createMemoryTokenStore } from "../auth/tokenStore";
import { ErrorCode } from "../constants/errorCode";
import { HttpStatus } from "../constants/httpStatus";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status: init.status ?? HttpStatus.OK,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

const envelope = <T,>(code: number, msg: string, data: T) => ({
  code,
  msg,
  data,
});

describe("createBaseApi parseResponse", () => {
  const baseUrl = "http://127.0.0.1:8000/api/v1";

  it("creates ApiError instances compatible with instanceof", () => {
    const error = new ApiError("bad", HttpStatus.BAD_REQUEST, ErrorCode.UNKNOWN_ERROR);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.name).toBe("ApiError");
  });

  it("extracts msg and code from envelope error bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        envelope(ErrorCode.USER_USERNAME_EXISTS, "用户名已存在", null),
        { status: HttpStatus.CONFLICT },
      ),
    );
    const { request } = createBaseApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(request("/users/1")).rejects.toMatchObject({
      message: "用户名已存在",
      status: HttpStatus.CONFLICT,
      code: ErrorCode.USER_USERNAME_EXISTS,
    });
  });

  it("falls back when error body is null", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(null, { status: HttpStatus.INTERNAL_SERVER_ERROR }),
    );
    const { request } = createBaseApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(request("/users/1")).rejects.toMatchObject({
      message: "请求失败",
      status: HttpStatus.INTERNAL_SERVER_ERROR,
    });
  });

  it("returns undefined for 204 responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: HttpStatus.NO_CONTENT }),
    );
    const { request } = createBaseApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(request("/noop")).resolves.toBeUndefined();
  });

  it("unwraps data from envelope success bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope(0, "success", { id: 1 }), {
        status: HttpStatus.OK,
      }),
    );
    const { request } = createBaseApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(request("/users/1")).resolves.toEqual({ id: 1 });
  });

  it("recognizes envelope without data field and treats missing data as undefined", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ code: 0, msg: "success" }, { status: HttpStatus.OK }),
    );
    const { request } = createBaseApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(request("/users/1")).resolves.toBeUndefined();
  });

  it("provides ApiError.is to compare business error codes", async () => {
    let rejected: ApiError | undefined;
    try {
      await createBaseApi({
        baseUrl,
        fetcher: vi.fn().mockResolvedValue(
          jsonResponse(
            envelope(ErrorCode.USER_USERNAME_EXISTS, "用户名已存在", null),
            { status: HttpStatus.CONFLICT },
          ),
        ),
        tokenStore: createMemoryTokenStore(),
      }).request("/users");
    } catch (err) {
      rejected = err as ApiError;
    }
    expect(rejected).toBeInstanceOf(ApiError);
    expect(rejected?.is(ErrorCode.USER_USERNAME_EXISTS)).toBe(true);
    expect(rejected?.is(ErrorCode.AUTH_CREDENTIALS_INVALID)).toBe(false);
  });
});
