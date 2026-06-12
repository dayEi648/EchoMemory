import type { TokenStore } from "../auth/tokenStore";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

export type ApiOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  tokenStore: TokenStore;
};

function extractErrorDetail(data: unknown): string | undefined {
  if (data === null || data === undefined) {
    return undefined;
  }
  if (typeof data === "string") {
    return data;
  }
  if (typeof data === "object" && "detail" in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return undefined;
}

export const createBaseApi = ({ baseUrl, fetcher, tokenStore }: ApiOptions) => {
  const requestFetcher = () => fetcher ?? globalThis.fetch;

  const parseResponse = async <T>(response: Response): Promise<T> => {
    if (response.status === 204) {
      return undefined as T;
    }
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    if (!response.ok) {
      throw new ApiError(extractErrorDetail(data) ?? "请求失败", response.status);
    }
    return data as T;
  };

  const refresh = async () => {
    const tokens = tokenStore.get();
    if (!tokens) {
      throw new ApiError("未登录", 401);
    }
    const response = await requestFetcher()(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    });
    const token = await parseResponse<{ access_token: string; refresh_token: string; token_type: string }>(response);
    tokenStore.set({ accessToken: token.access_token, refreshToken: token.refresh_token });
    return token;
  };

  const request = async <T>(path: string, init: RequestInit = {}, retry = true): Promise<T> => {
    const headers: Record<string, string> = {
      ...(init.headers as Record<string, string> | undefined),
    };
    const tokens = tokenStore.get();
    if (tokens) {
      headers.Authorization = `Bearer ${tokens.accessToken}`;
    }

    const response = await requestFetcher()(`${baseUrl}${path}`, { ...init, headers });
    if (response.status === 401 && retry && tokens) {
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
        tokenStore.clear();
        throw error;
      }
    }
    return parseResponse<T>(response);
  };

  return { request };
};
