import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "./authStore";
import { createMemoryTokenStore } from "../auth/tokenStore";
import { ErrorCode } from "../constants/errorCode";
import { HttpStatus } from "../constants/httpStatus";

const envelope = <T,>(data: T) => ({ code: 0, msg: "success", data });

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? HttpStatus.OK,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

const mockUser = {
  id: 1,
  username: "alice",
  nickname: "Alice",
  gender: 0,
  role: 0 as const,
  level: 2,
  exp: 400,
  city: null,
  birth: null,
  bio: null,
  is_verified: false,
  like_count: 0,
  avatar_url: null,
  created_at: null,
  email: null,
  phone: null,
  status: 0 as const,
  safety_score: 10,
  is_deleted: false,
  last_login_at: null,
  banned_at: null,
  ban_duration: null,
  is_official: false,
};

describe("authStore", () => {
  beforeEach(() => {
    const tokenStore = createMemoryTokenStore();
    useAuthStore.getState()._setTokenStore(tokenStore);
    useAuthStore.setState({ user: null, loading: false, initialized: false });
    vi.restoreAllMocks();
  });

  it("sets user to null when init finds no stored tokens", async () => {
    await useAuthStore.getState().init();

    const { user, loading, initialized } = useAuthStore.getState();
    expect(user).toBeNull();
    expect(loading).toBe(false);
    expect(initialized).toBe(true);
  });

  it("sets user when init successfully fetches /me", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(envelope(mockUser)));

    await useAuthStore.getState().init();

    expect(useAuthStore.getState().user).not.toBeNull();
    expect(useAuthStore.getState().user?.username).toBe("alice");
  });

  it("clears tokens and sets user null on 401 during init", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "expired", refreshToken: "rt" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        { code: ErrorCode.AUTH_CREDENTIALS_INVALID, msg: "expired", data: null },
        { status: HttpStatus.UNAUTHORIZED },
      ),
    );

    await useAuthStore.getState().init();

    expect(useAuthStore.getState().user).toBeNull();
    expect(tokenStore.get()).toBeNull();
  });

  it("login stores tokens and fetches user", async () => {
    const tokenStore = createMemoryTokenStore();
    useAuthStore.getState()._setTokenStore(tokenStore);
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse(
          envelope({
            access_token: "at",
            refresh_token: "rt",
            token_type: "bearer",
          }),
        ),
      )
      .mockResolvedValueOnce(jsonResponse(envelope(mockUser)));

    await useAuthStore.getState().login("alice", "secret");

    expect(tokenStore.get()).toEqual({ accessToken: "at", refreshToken: "rt" });
    expect(useAuthStore.getState().user?.username).toBe("alice");
  });

  it("logout clears user and calls API", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "at", refreshToken: "rt" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    useAuthStore.setState({
      user: mockUser,
      loading: false,
      initialized: true,
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: HttpStatus.NO_CONTENT }),
    );

    await useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(tokenStore.get()).toBeNull();
  });

  it("updateProfile updates user state with response", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "at", refreshToken: "rt" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    useAuthStore.setState({ user: mockUser, loading: false, initialized: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(envelope({ ...mockUser, nickname: "NewName", city: "北京" })),
    );

    await useAuthStore.getState().updateProfile({ nickname: "NewName", city: "北京" });

    const user = useAuthStore.getState().user;
    expect(user?.nickname).toBe("NewName");
    expect(user?.city).toBe("北京");
  });

  it("refreshUser does nothing on network error", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));
    useAuthStore.setState({ user: mockUser, loading: false, initialized: true });

    const ok = await useAuthStore.getState().refreshUser();

    expect(ok).toBe(false);
    expect(useAuthStore.getState().user?.username).toBe("alice");
  });

  it("clears tokens and user on 401 during refreshUser", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "expired", refreshToken: "rt" });
    useAuthStore.getState()._setTokenStore(tokenStore);
    useAuthStore.setState({ user: { ...mockUser, role: 2 }, loading: false, initialized: true });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(
        { code: ErrorCode.AUTH_TOKEN_REVOKED, msg: "revoked", data: null },
        { status: HttpStatus.UNAUTHORIZED },
      ),
    );

    const ok = await useAuthStore.getState().refreshUser();

    expect(ok).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
    expect(tokenStore.get()).toBeNull();
  });
});
