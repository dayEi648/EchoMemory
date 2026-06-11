import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { useAuthStore } from "./shared/stores/authStore";
import { createMemoryTokenStore } from "./shared/auth/tokenStore";
import type { UserMe, UserRole } from "./shared/api/types";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

const adminUser: UserMe = {
  id: 1,
  username: "admin",
  nickname: "Admin",
  gender: 0,
  role: 2,
  level: 4,
  exp: 1800,
  city: "上海",
  birth: null,
  bio: "curator",
  is_verified: true,
  like_count: 8,
  avatar_url: null,
  created_at: null,
  email: "admin@example.com",
  phone: null,
  status: 0,
  safety_score: 10,
  is_deleted: false,
  last_login_at: null,
  banned_at: null,
  ban_duration: null,
};

const makeUser = (overrides: Partial<UserMe> = {}): UserMe => ({
  ...adminUser,
  ...overrides,
});

const mockDiscoverApis = (user: UserMe, history: unknown[] = []) => {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = input instanceof Request ? input.url : String(input);
    if (url.includes("/auth/me")) {
      return jsonResponse(user);
    }
    if (url.includes("/music/")) {
      return jsonResponse({ items: [], total: 0 });
    }
    if (url.includes("/albums/")) {
      return jsonResponse({ items: [], total: 0 });
    }
    if (url.includes("/play-history/")) {
      return jsonResponse({ items: history, total: history.length });
    }
    return jsonResponse({});
  });
};

const renderApp = (options?: {
  initialEntries?: string[];
  tokenStore?: ReturnType<typeof createMemoryTokenStore>;
}) => {
  if (options?.tokenStore) {
    useAuthStore.getState()._setTokenStore(options.tokenStore);
  }

  return render(
    <MemoryRouter initialEntries={options?.initialEntries ?? ["/"]}>
      <App />
    </MemoryRouter>,
  );
};

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    const freshTokenStore = createMemoryTokenStore();
    useAuthStore.getState()._setTokenStore(freshTokenStore);
    useAuthStore.setState({ user: null, loading: true, initialized: false });
  });

  it("shows the auth screen when there is no session", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "回声记忆" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "注册" })).toBeInTheDocument();
  });

  it("renders discover page after loading the current user", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    mockDiscoverApis(adminUser);

    renderApp({ tokenStore });

    expect(await screen.findByText("欢迎回来，Admin")).toBeInTheDocument();
    expect(screen.getByText("发现音乐")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "个人中心" })).not.toBeInTheDocument();
  });

  it("renders discover page when play history music uses the backend compact shape", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = mockDiscoverApis(adminUser, [
      {
        id: 100,
        played_at: "2026-06-10T14:00:00Z",
        music: {
          id: 9,
          title: "No Author History Song",
          cover_icon_url: null,
        },
      },
    ]);

    renderApp({ tokenStore });

    expect(await screen.findByText("欢迎回来，Admin")).toBeInTheDocument();
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) => {
          const url = input instanceof Request ? input.url : String(input);
          return url.includes("/play-history/");
        }),
      ).toBe(true);
    });
    expect(await screen.findByText("No Author History Song")).toBeInTheDocument();
    expect(screen.getByText("未知艺人")).toBeInTheDocument();
  });

  it.each([
    { role: 0 as UserRole, username: "alice", nickname: "Alice" },
    { role: 1 as UserRole, username: "vip", nickname: "VIP User" },
  ])("redirects role $role users away from admin route and hides admin entry", async ({ role, nickname }) => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(makeUser({ role, username: "alice", nickname })));

    renderApp({ tokenStore, initialEntries: ["/admin"] });

    // 非管理员应被重定向到首页
    expect(await screen.findByText(`欢迎回来，${nickname}`)).toBeInTheDocument();

    // 管理后台不应显示
    expect(screen.queryByText("管理概览")).not.toBeInTheDocument();
    expect(screen.queryByText("用户管理")).not.toBeInTheDocument();
    expect(screen.queryByText("需要管理员权限")).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/users/admin/list"), expect.anything());
  });

  it.each([
    { role: 2 as UserRole, label: "管理员" },
    { role: 3 as UserRole, label: "超级管理员" },
  ])("lets $label users access and see the admin dashboard", async ({ role }) => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(makeUser({ role })));

    renderApp({ tokenStore, initialEntries: ["/admin"] });

    expect(await screen.findByText("管理概览")).toBeInTheDocument();
    expect(screen.getByText("用户管理")).toBeInTheDocument();
  });

  it("lets admin users navigate to admin from avatar menu", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(makeUser({ role: 2 })));

    renderApp({ tokenStore });

    expect(await screen.findByText("Admin")).toBeInTheDocument();

    // 打开头像菜单
    const avatarTrigger = screen.getByText("Admin");
    await userEvent.click(avatarTrigger);

    const adminEntry = screen.getByRole("button", { name: /管理后台/ });
    expect(adminEntry).toBeInTheDocument();

    await userEvent.click(adminEntry);

    expect(await screen.findByText("管理概览")).toBeInTheDocument();
  });

  it("hides admin entry in avatar menu for regular users", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(makeUser({ role: 0, nickname: "Alice" })));

    renderApp({ tokenStore });

    expect(await screen.findByText("Alice")).toBeInTheDocument();

    // 打开头像菜单
    const avatarTrigger = screen.getByText("Alice");
    await userEvent.click(avatarTrigger);

    expect(screen.queryByRole("button", { name: /管理后台/ })).not.toBeInTheDocument();
  });

  it("uses the city picker in account settings", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.includes("/auth/me")) return jsonResponse(adminUser);
        if (url.includes("/playlists/")) return jsonResponse({ items: [], total: 0 });
        return jsonResponse({});
      });

    renderApp({ tokenStore, initialEntries: ["/account"] });

    await screen.findByRole("heading", { name: "账号设置" });
    await screen.findByDisplayValue("上海");
    await userEvent.selectOptions(screen.getByLabelText("居住城市"), "成都");

    // Mock the PATCH response
    fetchMock.mockImplementation(async (input) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.includes("/users/me") || url.includes("/account")) return jsonResponse({ ...adminUser, city: "成都" });
      if (url.includes("/auth/me")) return jsonResponse(adminUser);
      if (url.includes("/playlists/")) return jsonResponse({ items: [], total: 0 });
      return jsonResponse({});
    });

    await userEvent.click(screen.getByRole("button", { name: "保存资料" }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(([input]) => {
        const url = input instanceof Request ? input.url : String(input);
        return url.includes("/users/me");
      });
      expect(patchCall).toBeTruthy();
    });
    const patchCall = fetchMock.mock.calls.find(([input]) => {
      const url = input instanceof Request ? input.url : String(input);
      return url.includes("/users/me");
    })!;
    const request = patchCall[1] as RequestInit;
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("city")).toBe("成都");
    expect((request.body as FormData).has("city_id")).toBe(false);
  });

  it("renders playlists page with API data", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.includes("/auth/me")) {
          return jsonResponse(adminUser);
        }
        if (url.includes("/playlists/")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({});
      });

    renderApp({ tokenStore, initialEntries: ["/playlists"] });

    expect(await screen.findByText("播放列表广场")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "暂无歌单" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/playlists/"), expect.anything());
  });

  it("renders space page with empty state", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = input instanceof Request ? input.url : String(input);
        if (url.includes("/auth/me")) {
          return jsonResponse(adminUser);
        }
        if (url.includes("/space-posts/")) {
          return jsonResponse({ items: [], total: 0 });
        }
        return jsonResponse({});
      });

    renderApp({ tokenStore, initialEntries: ["/space"] });

    expect(await screen.findByRole("heading", { name: "个人空间" })).toBeInTheDocument();
    expect(await screen.findByText("还没有发表过说说")).toBeInTheDocument();
  });
});
