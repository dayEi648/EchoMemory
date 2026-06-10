import type { TokenStore } from "../auth/tokenStore";
import type {
  LoginInput,
  PaginatedUsers,
  RegisterInput,
  TokenResponse,
  UpdateMeInput,
  UserAdminUpdate,
  UserMe,
  UserPublic,
  PaginatedUserSearch,
  UserSearchItem,
  UserStatus,
  UserTag,
} from "./types";

type ApiOptions = {
  baseUrl: string;
  fetcher?: typeof fetch;
  tokenStore: TokenStore;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

const toTokenPair = (token: TokenResponse) => ({
  accessToken: token.access_token,
  refreshToken: token.refresh_token,
});

import { appendDefined } from "../utils";


const toRegisterFormData = (input: RegisterInput) => {
  const formData = new FormData();
  appendDefined(formData, "username", input.username);
  appendDefined(formData, "nickname", input.nickname);
  appendDefined(formData, "password", input.password);
  appendDefined(formData, "email", input.email);
  appendDefined(formData, "phone", input.phone);
  appendDefined(formData, "gender", input.gender ?? 0);
  appendDefined(formData, "birth", input.birth);
  appendDefined(formData, "bio", input.bio);
  appendDefined(formData, "city", input.city);
  appendDefined(formData, "avatar", input.avatar);
  return formData;
};

const toUpdateFormData = (input: UpdateMeInput) => {
  const formData = new FormData();
  appendDefined(formData, "nickname", input.nickname);
  appendDefined(formData, "email", input.email);
  appendDefined(formData, "phone", input.phone);
  appendDefined(formData, "gender", input.gender);
  appendDefined(formData, "birth", input.birth);
  appendDefined(formData, "bio", input.bio);
  appendDefined(formData, "city", input.city);
  appendDefined(formData, "avatar", input.avatar);
  return formData;
};

export const createUserApi = ({ baseUrl, fetcher = fetch, tokenStore }: ApiOptions) => {
  const parseResponse = async <T>(response: Response): Promise<T> => {
    if (response.status === 204) {
      return undefined as T;
    }
    const data = (await response.json().catch(() => ({}))) as { detail?: string };
    if (!response.ok) {
      throw new ApiError(data.detail ?? "请求失败", response.status);
    }
    return data as T;
  };

  const refresh = async () => {
    const tokens = tokenStore.get();
    if (!tokens) {
      throw new ApiError("未登录", 401);
    }
    const response = await fetcher(`${baseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: tokens.refreshToken }),
    });
    const token = await parseResponse<TokenResponse>(response);
    tokenStore.set(toTokenPair(token));
    return token;
  };

  const request = async <T>(path: string, init: RequestInit = {}, retry = true): Promise<T> => {
    const headers: Record<string, string> = { ...(init.headers as Record<string, string> | undefined) };
    const tokens = tokenStore.get();
    if (tokens) {
      headers.Authorization = `Bearer ${tokens.accessToken}`;
    }

    const response = await fetcher(`${baseUrl}${path}`, { ...init, headers });
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

  return {
    login: async (input: LoginInput) => {
      const token = await request<TokenResponse>(
        "/auth/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(input),
        },
        false,
      );
      tokenStore.set(toTokenPair(token));
      return token;
    },
    register: async (input: RegisterInput) => {
      const token = await request<TokenResponse>(
        "/auth/register",
        {
          method: "POST",
          body: toRegisterFormData(input),
        },
        false,
      );
      tokenStore.set(toTokenPair(token));
      return token;
    },
    getMe: () => request<UserMe>("/auth/me"),
    updateMe: (input: UpdateMeInput) =>
      request<UserMe>("/users/me", { method: "PATCH", body: toUpdateFormData(input) }),
    searchUsers: (q: string, limit = 20, offset = 0) =>
      request<PaginatedUserSearch>(`/users/?q=${encodeURIComponent(q)}&limit=${limit}&offset=${offset}`, {}, false),
    getPublicUser: (userId: number) => request<UserPublic>(`/users/${userId}`, {}, false),
    getMyEmotionTags: () => request<UserTag[]>("/users/me/emotion-tags"),
    getMyInterestTags: () => request<UserTag[]>("/users/me/interest-tags"),
    follow: (followeeId: number) =>
      request<void>("/users/follow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ followee_id: followeeId }),
      }),
    unfollow: (followeeId: number) =>
      request<void>("/users/unfollow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ followee_id: followeeId }),
      }),
    adminListUsers: (params: {
      q?: string;
      role?: number;
      status?: number;
      isDeleted?: boolean;
      sortBy?: string;
      sortOrder?: string;
      limit?: number;
      offset?: number;
    }) => {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.q) query.set("q", params.q);
      if (params.role !== undefined) query.set("role", String(params.role));
      if (params.status !== undefined) query.set("status", String(params.status));
      if (params.isDeleted !== undefined) query.set("is_deleted", String(params.isDeleted));
      if (params.sortBy) query.set("sort_by", params.sortBy);
      if (params.sortOrder) query.set("sort_order", params.sortOrder);
      return request<PaginatedUsers>(`/users/admin/list?${query.toString()}`);
    },
    adminUpdateUser: (userId: number, input: UserAdminUpdate) =>
      request<UserMe>(`/users/${userId}/admin`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
      }),
    adminBanUser: (userId: number, status: Exclude<UserStatus, 0>, banDuration?: string) =>
      request<UserMe>(`/users/${userId}/ban`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, ban_duration: banDuration }),
      }),
    adminUnbanUser: (userId: number) => request<UserMe>(`/users/${userId}/unban`, { method: "POST" }),
    adminGetUserFull: (userId: number) => request<UserMe>(`/users/${userId}/admin`),
    adminDeleteUser: (userId: number) =>
      request<void>(`/users/${userId}/admin`, { method: "DELETE" }),
    logout: async () => {
      const tokens = tokenStore.get();
      if (!tokens) {
        return;
      }
      await request<void>(
        "/auth/logout",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: tokens.refreshToken }),
        },
        false,
      ).finally(() => tokenStore.clear());
    },
  };
};
