import { describe, expect, it, vi } from "vitest";

import { parseSSELine, createAIConversationApi } from "./aiConversationApi";
import { createMemoryTokenStore } from "../auth/tokenStore";

const baseUrl = "http://127.0.0.1:8000/api/v1";

describe("parseSSELine", () => {
  it("returns null for empty lines", () => {
    expect(parseSSELine("")).toBeNull();
    expect(parseSSELine("   ")).toBeNull();
  });

  it("returns null for comment lines", () => {
    expect(parseSSELine(": ping")).toBeNull();
  });

  it("returns null for lines without data prefix", () => {
    expect(parseSSELine("event: message")).toBeNull();
  });

  it("parses content chunks", () => {
    const chunk = parseSSELine('data: {"type":"content","data":"你好","model":"deepseek-v4-flash"}');
    expect(chunk).toEqual({
      type: "content",
      data: "你好",
      model: "deepseek-v4-flash",
    });
  });

  it("parses reasoning chunks", () => {
    const chunk = parseSSELine('data: {"type":"reasoning","data":"思考中","model":"deepseek-v4-flash"}');
    expect(chunk).toEqual({
      type: "reasoning",
      data: "思考中",
      model: "deepseek-v4-flash",
    });
  });

  it("parses error chunks", () => {
    const chunk = parseSSELine('data: {"type":"error","data":"失败","model":null}');
    expect(chunk).toEqual({
      type: "error",
      data: "失败",
      model: null,
    });
  });

  it("parses done marker", () => {
    expect(parseSSELine("data: [DONE]")).toEqual({
      type: "done",
      data: "",
      model: null,
    });
  });

  it("returns null for invalid json", () => {
    expect(parseSSELine("data: not-json")).toBeNull();
  });
});

describe("createAIConversationApi streamMessage", () => {
  function createStreamResponse(chunks: string[]) {
    const encoder = new TextEncoder();
    let index = 0;
    return new Response(
      new ReadableStream({
        pull(controller) {
          if (index < chunks.length) {
            controller.enqueue(encoder.encode(chunks[index]));
            index += 1;
          } else {
            controller.close();
          }
        },
      }),
      {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      },
    );
  }

  it("yields content and done chunks from SSE stream", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      createStreamResponse([
        'data: {"type":"content","data":"你","model":"deepseek-v4-flash"}\n\n',
        'data: {"type":"content","data":"好","model":"deepseek-v4-flash"}\n\n',
        "data: [DONE]\n\n",
      ]),
    );

    const api = createAIConversationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    const chunks: ReturnType<typeof parseSSELine>[] = [];
    for await (const chunk of api.streamMessage(1, "hi")) {
      chunks.push(chunk);
    }

    expect(chunks).toEqual([
      { type: "content", data: "你", model: "deepseek-v4-flash" },
      { type: "content", data: "好", model: "deepseek-v4-flash" },
      { type: "done", data: "", model: null },
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/ai/conversations/1/messages`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        }),
        body: JSON.stringify({ content: "hi", stream: true }),
      }),
    );
  });

  it("throws when response is not ok", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("server error", { status: 500 }),
    );

    const api = createAIConversationApi({
      baseUrl,
      fetcher: fetchMock,
      tokenStore: createMemoryTokenStore(),
    });

    await expect(async () => {
      for await (const _ of api.streamMessage(1, "hi")) {
        // noop
      }
    }).rejects.toThrow("server error");
  });
});

describe("createAIConversationApi JSON endpoints", () => {
  const tokenStore = createMemoryTokenStore();
  tokenStore.set({ accessToken: "token", refreshToken: "refresh" });

  it("lists conversations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 0,
          msg: "success",
          data: { items: [{ id: 1, title: "新对话" }], total: 1 },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );

    const api = createAIConversationApi({ baseUrl, fetcher: fetchMock, tokenStore });
    const result = await api.listConversations();
    expect(result.items).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it("updates conversation title", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: 0,
          msg: "success",
          data: { id: 1, title: "新标题" },
        }),
        { headers: { "Content-Type": "application/json" } },
      ),
    );

    const api = createAIConversationApi({ baseUrl, fetcher: fetchMock, tokenStore });
    const result = await api.updateTitle(1, "新标题");
    expect(result.title).toBe("新标题");
    expect(fetchMock).toHaveBeenCalledWith(
      `${baseUrl}/ai/conversations/1`,
      expect.objectContaining({
        method: "PATCH",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer token",
        }),
        body: JSON.stringify({ title: "新标题" }),
      }),
    );
  });
});
