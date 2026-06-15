import { create } from "zustand";

import { createUserApi, type ApiError } from "../api/userApi";
import { replaceApiTokenStore, API_BASE_URL } from "../api/instances";
import { HttpStatus } from "../constants/httpStatus";
import type { UpdateMeInput, UserMe } from "../api/types";
import { createLocalStorageTokenStore, type TokenStore } from "../auth/tokenStore";

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
  refreshUser: () => Promise<boolean>;
}

const defaultTokenStore = createLocalStorageTokenStore();
let currentTokenStore = defaultTokenStore;
let currentApi = createUserApi({ baseUrl: API_BASE_URL, tokenStore: currentTokenStore });

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  initialized: false,
  tokenStore: currentTokenStore,
  api: currentApi,

  _setTokenStore: (ts: TokenStore) => {
    currentTokenStore = ts;
    currentApi = createUserApi({ baseUrl: API_BASE_URL, tokenStore: ts });
    replaceApiTokenStore(ts);
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
      if (apiErr.status === HttpStatus.UNAUTHORIZED) {
        currentTokenStore.clear();
      }
      set({ user: null, loading: false, initialized: true });
    }
  },

  login: async (username, password) => {
    await currentApi.login({ username, password });
    try {
      const user = await currentApi.getMe();
      set({ user });
    } catch {
      currentTokenStore.clear();
      throw new Error("登录后获取用户信息失败，请重试");
    }
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
    try {
      const user = await currentApi.getMe();
      set({ user });
    } catch {
      currentTokenStore.clear();
      throw new Error("注册后获取用户信息失败，请重试");
    }
  },

  logout: async () => {
    await currentApi.logout();
    set({ user: null });
  },

  updateProfile: async (input) => {
    const user = await currentApi.updateMe(input);
    set({ user });
  },

  refreshUser: async (): Promise<boolean> => {
    const tokens = currentTokenStore.get();
    if (!tokens) {
      set({ user: null });
      return false;
    }
    try {
      const user = await currentApi.getMe();
      set({ user });
      return true;
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === HttpStatus.UNAUTHORIZED) {
        currentTokenStore.clear();
        set({ user: null });
      } else if (apiErr.status === HttpStatus.FORBIDDEN) {
        set({ user: null });
      }
      return false;
    }
  },
}));
