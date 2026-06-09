import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { createMemoryTokenStore } from "./shared/auth/tokenStore";
import type { UserMe } from "./shared/api/types";

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
  last_login_at: null,
  banned_at: null,
  ban_duration: null,
};

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.location.hash = "";
  });

  it("shows the auth screen when there is no session", async () => {
    render(<App tokenStore={createMemoryTokenStore()} />);

    expect(await screen.findByRole("heading", { name: "回声记忆" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登录" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "注册" })).toBeInTheDocument();
  });

  it("renders user home after loading the current user", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(adminUser));

    render(<App tokenStore={tokenStore} />);

    expect(await screen.findByText("Admin")).toBeInTheDocument();
    expect(screen.getByText("Lv.4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "个人中心" })).toBeInTheDocument();
  });

  it("blocks normal users from user administration", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ ...adminUser, role: 0, username: "alice", nickname: "Alice" }),
    );

    render(<App tokenStore={tokenStore} initialRoute="admin" />);

    expect(await screen.findByText("需要管理员权限")).toBeInTheDocument();
  });

  it("uses the city picker value in profile editing", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(adminUser))
      .mockResolvedValueOnce(jsonResponse({ ...adminUser, city: "成都" }));

    render(<App tokenStore={tokenStore} initialRoute="profile" />);

    await screen.findByDisplayValue("上海");
    await userEvent.selectOptions(screen.getByLabelText("居住城市"), "成都");
    await userEvent.click(screen.getByRole("button", { name: "保存资料" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const request = fetchMock.mock.calls[1][1] as RequestInit;
    expect(request.body).toBeInstanceOf(FormData);
    expect((request.body as FormData).get("city")).toBe("成都");
    expect((request.body as FormData).has("city_id")).toBe(false);
  });

  it("keeps non-user modules as placeholders without calling their APIs", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "access", refreshToken: "refresh" });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(adminUser));

    render(<App tokenStore={tokenStore} initialRoute="music" />);

    expect(await screen.findByText("音乐模块占位")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalledWith(expect.stringContaining("/music"), expect.anything());
  });
});
