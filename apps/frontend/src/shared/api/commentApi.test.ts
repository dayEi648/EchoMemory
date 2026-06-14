import { describe, expect, it, vi } from "vitest";

import { createCommentApi } from "./commentApi";
import { createMemoryTokenStore } from "../auth/tokenStore";
import { HttpStatus } from "../constants/httpStatus";

const envelope = <T,>(data: T) => ({ code: 0, msg: "success", data });

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: init.status ?? HttpStatus.OK,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

const baseUrl = "http://127.0.0.1:8000/api/v1";

describe("commentApi", () => {
  const tokenStore = createMemoryTokenStore();

  it("passes sort_by parameter in listRootComments", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    const api = createCommentApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await api.listRootComments("music", 1, { sort_by: "likes" });

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("sort_by=likes");
  });

  it("defaults to no sort_by when not specified", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(envelope({ items: [], total: 0 })),
    );
    const api = createCommentApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await api.listRootComments("music", 1);

    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).not.toContain("sort_by");
  });

  it("sends correct JSON body on createComment", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        envelope({
          id: 1,
          content: "Nice!",
          user: { id: 2, username: "alice", nickname: "Alice", avatar_url: null },
          like_count: 0,
          dislike_count: 0,
          reply_count: 0,
          parent_id: null,
          root_id: null,
          is_nested_reply: false,
          created_at: "2026-01-01T00:00:00Z",
        }),
      ),
    );
    tokenStore.set({ accessToken: "token", refreshToken: "rt" });
    const api = createCommentApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await api.createComment({
      target_type: "music",
      target_id: 42,
      content: "Nice!",
    });

    const [, request] = fetchMock.mock.calls[0];
    expect(request.method).toBe("POST");
    expect(JSON.parse(request.body as string)).toEqual({
      target_type: "music",
      target_id: 42,
      content: "Nice!",
    });
  });

  it("handles dislike and undislike endpoints", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, { status: HttpStatus.NO_CONTENT }),
    );
    tokenStore.set({ accessToken: "token", refreshToken: "rt" });
    const api = createCommentApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await api.dislikeComment(10);
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("/comments/10/dislike"),
      expect.objectContaining({ method: "POST" }),
    );

    await api.undislikeComment(10);
    expect(fetchMock).toHaveBeenLastCalledWith(
      expect.stringContaining("/comments/10/dislike"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("retrieves replies for a root comment", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(envelope([])));
    const api = createCommentApi({ baseUrl, fetcher: fetchMock, tokenStore });

    await api.listReplies(5);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/comments/replies/5"),
      expect.anything(),
    );
  });
});
