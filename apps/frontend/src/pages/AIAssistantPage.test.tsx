import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIAssistantPage } from "./AIAssistantPage";
import { aiConversationApi } from "../shared/api/instances";

vi.mock("../shared/api/instances", () => ({
  aiConversationApi: {
    listConversations: vi.fn(),
    getMessages: vi.fn(),
    streamFirstMessage: vi.fn(),
    streamMessage: vi.fn(),
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

describe("AIAssistantPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
