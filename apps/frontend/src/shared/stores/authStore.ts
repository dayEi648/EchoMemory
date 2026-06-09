import { create } from "zustand";

import { createUserApi, type ApiError } from "../api/userApi";
import type { UpdateMeInput, UserMe } from "../api/types";
import { createMemoryTokenStore, type TokenStore } from "../auth/tokenStore";

const isDev = import.meta.env.DEV;
const envBaseUrl = import.meta.env.VITE_API_BASE_URL;

if (!isDev && !envBaseUrl) {
  throw new Error(
    "生产环境必须配置 VITE_API_BASE_URL。" +
    "请在 apps/frontend/.env.production 中设置后端 API 地址，" +
    "例如：VITE_API_BASE_URL=https://api.echomemory.com/api/v1",
  );
}

const API_BASE_URL = envBaseUrl ?? "/api/v1";

export type RegisterFormData = {
  username: string;
  nickname: string;
  password: string;
  email?: string;
  gender?: number;
  city?: string;
};

interface AuthState {
  user: UserMe | null;
  loading: boolean;
  initialized: boolean;
  tokenStore: TokenStore;
  api: ReturnType<typeof createUserApi>;

  _setTokenStore: (ts: TokenStore) => void;
  init: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (data: RegisterFormData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (input: UpdateMeInput) => Promise<void>;
  refreshUser: () => Promise<void>;
}

const defaultTokenStore = createMemoryTokenStore();
let currentTokenStore = defaultTokenStore;
let currentApi = createUserApi({ baseUrl: API_BASE_URL, tokenStore: currentTokenStore });

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loading: true,
  initialized: false,
  tokenStore: currentTokenStore,
  api: currentApi,

  _setTokenStore: (ts: TokenStore) => {
    currentTokenStore = ts;
    currentApi = createUserApi({ baseUrl: API_BASE_URL, tokenStore: ts });
    set({ tokenStore: ts, api: currentApi });
  },

  init: async () => {
    const tokens = currentTokenStore.get();
    if (!tokens) {
      set({ loading: false, initialized: true });
      return;
    }
    try {
      const user = await currentApi.getMe();
      set({ user, loading: false, initialized: true });
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 401) {
        currentTokenStore.clear();
      }
      set({ user: null, loading: false, initialized: true });
    }
  },

  login: async (username, password) => {
    await currentApi.login({ username, password });
    const user = await currentApi.getMe();
    set({ user });
  },

  register: async (data) => {
    await currentApi.register({
      username: data.username,
      nickname: data.nickname,
      password: data.password,
      email: data.email,
      gender: data.gender ?? 0,
      city: data.city,
    });
    const user = await currentApi.getMe();
    set({ user });
  },

  logout: async () => {
    await currentApi.logout();
    set({ user: null });
  },

  updateProfile: async (input) => {
    const user = await currentApi.updateMe(input);
    set({ user });
  },

  refreshUser: async () => {
    try {
      const user = await currentApi.getMe();
      set({ user });
    } catch {
      // silently fail
    }
  },
}));
