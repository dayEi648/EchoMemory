import type { TokenStore } from "../auth/tokenStore";
import { ErrorCode, getErrorCodeDescription } from "../constants/errorCode";
import { HttpStatus } from "../constants/httpStatus";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: number,
  ) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  /** 判断业务错误码是否匹配给定枚举。 */
  is(code: ErrorCode): boolean {
    return this.code === code;
  }
}

export type ApiResponse<T> = {
  code: number;
  msg: string;
  data: T;
};

export type ApiOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  tokenStore: TokenStore;
};

function extractEnvelopeError(envelope: unknown): string | undefined {
  if (envelope === null || envelope === undefined) {
    return undefined;
  }
  if (typeof envelope !== "object") {
    return undefined;
  }
  const msg = (envelope as { msg?: unknown }).msg;
  if (typeof msg === "string") {
    return msg;
  }
  return undefined;
}

export const createBaseApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const requestFetcher = () => fetcher ?? globalThis.fetch;

  const parseResponse = async <T>(response: Response): Promise<T> => {
    if (response.status === HttpStatus.NO_CONTENT) {
      return undefined as T;
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    // 后端统一返回 {code, msg, data} 信封
    if (isApiResponse(payload)) {
      if (payload.code !== ErrorCode.SUCCESS) {
        const msg = payload.msg || getErrorCodeDescription(payload.code);
        throw new ApiError(msg, response.status, payload.code);
      }
      return payload.data as T;
    }

    // 兼容非信封错误（如 Nginx 直接返回的 HTML/JSON）
    if (!response.ok) {
      const msg = extractEnvelopeError(payload) ?? "请求失败";
      throw new ApiError(msg, response.status);
    }

    // 兼容非信封成功响应（不应再出现）
    return payload as T;
  };

  /** 互斥锁：防止并发 401 同时刷新 token */
  let refreshPromise: Promise<{
    access_token: string;
    refresh_token: string;
    token_type: string;
  }> | null = null;

  const refresh = async () => {
    if (refreshPromise) return refreshPromise;

    refreshPromise = (async () => {
      const tokens = tokenStore.get();
      if (!tokens) {
        throw new ApiError("未登录", HttpStatus.UNAUTHORIZED, ErrorCode.AUTH_REFRESH_TOKEN_INVALID);
      }
      const response = await requestFetcher()(`${baseUrl}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refreshToken }),
      });
      const token = await parseResponse<{
        access_token: string;
        refresh_token: string;
        token_type: string;
      }>(response);
      tokenStore.set({
        accessToken: token.access_token,
        refreshToken: token.refresh_token,
      });
      return token;
    })();

    try {
      return await refreshPromise;
    } finally {
      refreshPromise = null;
    }
  };

  const request = async <T>(
    path: string,
    init: RequestInit = {},
    retry = true,
  ): Promise<T> => {
    const headers: Record<string, string> = {
      ...(init.headers as Record<string, string> | undefined),
    };
    const tokens = tokenStore.get();
    if (tokens) {
      headers.Authorization = `Bearer ${tokens.accessToken}`;
    }

    const response = await requestFetcher()(`${baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (response.status === HttpStatus.UNAUTHORIZED && retry && tokens) {
      try {
        const refreshed = await refresh();
        return request<T>(
          path,
          {
            ...init,
            headers: {
              ...(init.headers as Record<string, string> | undefined),
              Authorization: `Bearer ${refreshed.access_token}`,
            },
          },
          false,
        );
      } catch (error) {
        // 仅当 refresh 本身返回 401 时才清 token（网络故障保留 token）
        if (
          error instanceof ApiError &&
          error.status === HttpStatus.UNAUTHORIZED
        ) {
          tokenStore.clear();
        }
        throw error;
      }
    }
    return parseResponse<T>(response);
  };

  return { request };
};

function isApiResponse(payload: unknown): payload is ApiResponse<unknown> {
  return (
    typeof payload === "object" &&
    payload !== null &&
    "code" in payload &&
    "msg" in payload &&
    typeof (payload as { code?: unknown }).code === "number" &&
    typeof (payload as { msg?: unknown }).msg === "string"
  );
}
