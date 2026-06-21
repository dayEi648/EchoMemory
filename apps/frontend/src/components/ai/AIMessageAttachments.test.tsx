import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AIMessageAttachments } from "./AIMessageAttachments";
import type { AIConversationAttachment } from "../../shared/api/types";


describe("AIMessageAttachments", () => {
  it("renders a music card with separate play and detail actions", async () => {
    const onOpen = vi.fn();
    const onPlayMusic = vi.fn();
    const attachment: AIConversationAttachment = {
      version: 1,
      type: "music_card",
      items: [
        {
          id: 12,
          title: "回声",
          authors: ["歌手甲"],
          album: "夜色",
          cover_url: null,
          is_vip: false,
        },
      ],
    };

    render(
      <AIMessageAttachments
        attachments={[attachment]}
        onOpen={onOpen}
        onPlayMusic={onPlayMusic}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByText("回声")).toBeVisible();
    expect(screen.getByText("歌手甲 · 夜色")).toBeVisible();

    await userEvent.click(screen.getByRole("button", { name: "播放回声" }));
    expect(onPlayMusic).toHaveBeenCalledWith(12);

    await userEvent.click(screen.getByRole("button", { name: "查看音乐回声" }));
    expect(onOpen).toHaveBeenCalledWith("music", 12);
  });

  it("renders playlist and album cards with distinct labels", () => {
    const attachments: AIConversationAttachment[] = [
      {
        version: 1,
        type: "playlist_card",
        items: [
          {
            id: 21,
            title: "通勤歌单",
            creator: "小回",
            description: "适合清晨",
            cover_url: null,
            music_count: 18,
          },
        ],
      },
      {
        version: 1,
        type: "album_card",
        items: [
          {
            id: 31,
            title: "冬日专辑",
            authors: ["创作者乙"],
            description: null,
            cover_url: null,
            music_count: 9,
          },
        ],
      },
    ];

    render(
      <AIMessageAttachments
        attachments={attachments}
        onOpen={vi.fn()}
        onPlayMusic={vi.fn()}
        onConfirm={vi.fn()}
        onCancelConfirmation={vi.fn()}
      />,
    );

    expect(screen.getByText("歌单 · 18 首")).toBeVisible();
    expect(screen.getByText("专辑 · 9 首")).toBeVisible();
  });

  it("requires an explicit confirmation button before invoking a write callback", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const attachment: AIConversationAttachment = {
      version: 1,
      type: "confirmation_card",
      resource_type: "music",
      action: "collect",
      resource: {
        id: 7,
        title: "待收藏歌曲",
        cover_url: null,
      },
      confirmation_token: "signed-token",
      prompt: "确认收藏音乐《待收藏歌曲》吗？",
    };

    render(
      <AIMessageAttachments
        attachments={[attachment]}
        onOpen={vi.fn()}
        onPlayMusic={vi.fn()}
        onConfirm={onConfirm}
        onCancelConfirmation={onCancel}
      />,
    );

    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "确认收藏" }));
    expect(onConfirm).toHaveBeenCalledWith(attachment);

    await userEvent.click(screen.getByRole("button", { name: "取消操作" }));
    expect(onCancel).toHaveBeenCalledWith("signed-token");
  });
});
