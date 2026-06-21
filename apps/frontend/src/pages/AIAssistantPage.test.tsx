import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIAssistantPage } from "./AIAssistantPage";
import { aiConversationApi } from "../shared/api/instances";
import { useAuthStore } from "../shared/stores/authStore";
import type { UserMe } from "../shared/api/types";

vi.mock("../shared/api/instances", () => ({
  API_BASE_URL: "http://127.0.0.1:8000/api/v1",
  aiConversationApi: {
    listConversations: vi.fn(),
    getMessages: vi.fn(),
    streamFirstMessage: vi.fn(),
    streamMessage: vi.fn(),
    updateTitle: vi.fn(),
    deleteConversation: vi.fn(),
  },
}));

const conversation = {
  id: 1,
  user_id: 7,
  title: "新对话",
  model: "deepseek-v4-flash",
  status: 0,
  thread_id: "1",
  updated_at: "2026-06-20T10:00:00Z",
  created_at: "2026-06-20T10:00:00Z",
};

const normalUser = {
  id: 7,
  username: "user",
  nickname: "用户",
  gender: 0,
  role: 0,
  level: 1,
  exp: 0,
  city: null,
  birth: null,
  bio: null,
  is_verified: false,
  is_official: false,
  like_count: 0,
  avatar_url: null,
  created_at: null,
  email: null,
  phone: null,
  status: 0,
  safety_score: 10,
  is_deleted: false,
  last_login_at: null,
  banned_at: null,
  ban_duration: null,
} satisfies UserMe;

describe("AIAssistantPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: normalUser });
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({ messages: [] });
  });

  it("keeps the first user message before exactly one assistant response", async () => {
    vi.mocked(aiConversationApi.streamFirstMessage).mockImplementation(async function* () {
      yield {
        type: "content",
        data: "",
        model: conversation.model,
        meta: { conversation },
      };
      yield {
        type: "reasoning",
        data: "先理解用户问题。",
        model: conversation.model,
      };
      yield {
        type: "content",
        data: "你好，我是回声记忆助手。",
        model: conversation.model,
      };
      yield { type: "done", data: "", model: conversation.model };
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("button", { name: "新建对话" }));
    const input = screen.getByPlaceholderText("输入消息，Enter 发送，Shift+Enter 换行");
    await userEvent.type(input, "你好");
    await userEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("你好，我是回声记忆助手。");

    const renderedMessages = document.querySelectorAll(".ai-assistant-message");
    expect(renderedMessages).toHaveLength(2);
    expect(renderedMessages[0]).toHaveClass("user");
    expect(renderedMessages[0]).toHaveTextContent("你好");
    expect(renderedMessages[1]).toHaveClass("ai");
    expect(renderedMessages[1]).toHaveTextContent("你好，我是回声记忆助手。");
    expect(screen.queryByText(/<thinking>|<answer>/)).not.toBeInTheDocument();
    expect(aiConversationApi.getMessages).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "已深度思考" }));
    expect(screen.getByText("先理解用户问题。")).toBeVisible();
  });

  it("restores persisted reasoning in a collapsible panel", async () => {
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({
      messages: [
        { role: "human", content: "推荐一首歌" },
        {
          role: "ai",
          content: "可以听听《夜曲》。",
          reasoning_content: "根据用户想听歌的意图给出简洁建议。",
        },
      ],
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    await screen.findByText("可以听听《夜曲》。");
    await userEvent.click(screen.getByRole("button", { name: "已深度思考" }));

    await waitFor(() => {
      expect(screen.getByText("根据用户想听歌的意图给出简洁建议。")).toBeVisible();
    });
  });

  it("restores persisted resource cards from conversation history", async () => {
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({
      messages: [
        { role: "human", content: "推荐一首歌" },
        {
          role: "ai",
          content: "这首适合你。",
          attachments: [
            {
              version: 1,
              type: "music_card",
              items: [
                {
                  id: 88,
                  title: "持久回声",
                  authors: ["回声歌手"],
                  album: null,
                  cover_url: null,
                  is_vip: false,
                },
              ],
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    expect(await screen.findByText("持久回声")).toBeVisible();
    expect(screen.getByRole("button", { name: "播放持久回声" })).toBeVisible();
  });

  it("streams a confirmation card and sends its token only after button confirmation", async () => {
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.streamMessage).mockImplementation(async function* () {
      yield { type: "content", data: "已完成。", model: conversation.model };
      yield { type: "done", data: "", model: conversation.model };
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({
      messages: [
        {
          role: "ai",
          content: "请确认操作。",
          attachments: [
            {
              version: 1,
              type: "confirmation_card",
              resource_type: "music",
              action: "collect",
              resource: {
                id: 9,
                title: "确认之歌",
                cover_url: null,
              },
              confirmation_token: "signed-token",
              prompt: "确认收藏音乐《确认之歌》吗？",
            },
          ],
        },
      ],
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    expect(aiConversationApi.streamMessage).not.toHaveBeenCalled();

    await userEvent.click(await screen.findByRole("button", { name: "确认收藏" }));

    await waitFor(() => {
      expect(aiConversationApi.streamMessage).toHaveBeenCalledWith(
        1,
        "我确认收藏《确认之歌》。",
        { confirmationToken: "signed-token" },
      );
    });
  });

  it("does not show internal message filters to normal users", async () => {
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));

    expect(screen.queryByRole("group", { name: "消息类型筛选" })).not.toBeInTheDocument();
    expect(aiConversationApi.getMessages).toHaveBeenCalledWith(1, {
      messageTypes: ["human", "ai"],
    });
  });

  it("lets administrators filter all persisted message types", async () => {
    useAuthStore.setState({
      user: { ...normalUser, role: 2, nickname: "管理员" },
    });
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({
      messages: [
        { role: "system", content: "system prompt" },
        { role: "human", content: "搜索新闻" },
        {
          role: "tool",
          content: '[{"type":"text","text":"# 搜索结果"}]',
          name: "search_web",
          tool_call_id: "call-1",
        },
        { role: "ai", content: "最终回答" },
      ],
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    const filterGroup = screen.getByRole("group", { name: "消息类型筛选" });
    expect(filterGroup).toBeVisible();

    await userEvent.click(screen.getByRole("checkbox", { name: "系统" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "工具" }));

    await waitFor(() => {
      expect(aiConversationApi.getMessages).toHaveBeenLastCalledWith(1, {
        messageTypes: ["system", "human", "ai", "tool"],
      });
    });
    expect(await screen.findByText("system prompt")).toBeVisible();
    expect(screen.getByText(/搜索结果/)).toBeVisible();
  });

  it("lets administrators collapse and reopen the message filter panel", async () => {
    useAuthStore.setState({
      user: { ...normalUser, role: 2, nickname: "管理员" },
    });
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));

    const toggle = screen.getByRole("button", { name: "收起消息视图筛选" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("checkbox", { name: "系统" })).toBeVisible();

    await userEvent.click(toggle);

    expect(
      screen.getByRole("button", { name: "展开消息视图筛选" }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(
      screen.queryByRole("checkbox", { name: "系统" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("用户、AI")).toBeVisible();

    await userEvent.click(
      screen.getByRole("button", { name: "展开消息视图筛选" }),
    );

    expect(screen.getByRole("checkbox", { name: "系统" })).toBeVisible();
  });

  it("resets to the safe message view after an administrator is downgraded", async () => {
    useAuthStore.setState({
      user: { ...normalUser, role: 2, nickname: "管理员" },
    });
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    await userEvent.click(screen.getByRole("checkbox", { name: "工具" }));

    useAuthStore.setState({ user: normalUser });

    await waitFor(() => {
      expect(
        screen.queryByRole("group", { name: "消息类型筛选" }),
      ).not.toBeInTheDocument();
      expect(aiConversationApi.getMessages).toHaveBeenLastCalledWith(1, {
        messageTypes: ["human", "ai"],
      });
    });
  });

  it("retries a failed response without duplicating the user message", async () => {
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({ messages: [] });
    vi.mocked(aiConversationApi.streamMessage)
      .mockImplementationOnce(async function* () {
        yield { type: "error", data: "暂时失败", model: conversation.model };
      })
      .mockImplementationOnce(async function* () {
        yield {
          type: "content",
          data: "重试成功",
          model: conversation.model,
        };
        yield { type: "done", data: "", model: conversation.model };
      });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    const input = screen.getByPlaceholderText("输入消息，Enter 发送，Shift+Enter 换行");
    await userEvent.type(input, "你好");
    await userEvent.click(screen.getByRole("button", { name: "发送消息" }));
    await userEvent.click(await screen.findByRole("button", { name: "重试" }));

    await screen.findByText("重试成功");
    const userMessages = document.querySelectorAll(".ai-assistant-message.user");
    expect(userMessages).toHaveLength(1);
    expect(userMessages[0]).toHaveTextContent("你好");
  });
});


  it("allows editing the conversation title", async () => {
    const updatedConversation = { ...conversation, title: "自定义标题" };
    vi.mocked(aiConversationApi.listConversations).mockResolvedValue({
      items: [conversation],
      total: 1,
    });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({ messages: [] });
    vi.mocked(aiConversationApi.updateTitle).mockResolvedValue(updatedConversation);

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(await screen.findByText("新对话"));
    await userEvent.click(screen.getByTitle("点击修改标题"));

    const titleInput = screen.getByDisplayValue("新对话");
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "自定义标题");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByTitle("点击修改标题")).toHaveTextContent("自定义标题");
    });
    expect(aiConversationApi.updateTitle).toHaveBeenCalledWith(1, "自定义标题");
  });

  it("refreshes the conversation list after the first streamed message", async () => {
    const titledConversation = { ...conversation, title: "生成的标题" };
    vi.mocked(aiConversationApi.listConversations)
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValueOnce({ items: [titledConversation], total: 1 });
    vi.mocked(aiConversationApi.getMessages).mockResolvedValue({ messages: [] });
    vi.mocked(aiConversationApi.streamFirstMessage).mockImplementation(async function* () {
      yield {
        type: "content",
        data: "",
        model: conversation.model,
        meta: { conversation },
      };
      yield {
        type: "content",
        data: "AI 回复内容",
        model: conversation.model,
      };
      yield { type: "done", data: "", model: conversation.model };
    });

    render(
      <MemoryRouter>
        <AIAssistantPage />
      </MemoryRouter>,
    );

    await userEvent.click(screen.getByRole("button", { name: "新建对话" }));
    const input = screen.getByPlaceholderText("输入消息，Enter 发送，Shift+Enter 换行");
    await userEvent.type(input, "你好");
    await userEvent.click(screen.getByRole("button", { name: "发送消息" }));

    await screen.findByText("AI 回复内容");

    await waitFor(() => {
      expect(screen.getByTitle("点击修改标题")).toHaveTextContent("生成的标题");
    });
    expect(aiConversationApi.listConversations).toHaveBeenCalled();
  });
