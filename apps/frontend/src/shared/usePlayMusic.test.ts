import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePlayMusic } from "./usePlayMusic";
import { musicApi } from "./api/instances";
import { usePlayerStore } from "./stores/playerStore";
import type { MusicDetail, MusicListItem } from "./api/types";

vi.mock("./api/instances", () => ({
  musicApi: {
    getMusicDetail: vi.fn(),
  },
}));

vi.mock("./stores/playerStore", () => ({
  usePlayerStore: vi.fn(),
}));

const mockMusicListItem: MusicListItem = {
  id: 2,
  title: "List Song",
  is_vip: false,
  hot: 0,
  play_count: 0,
  cover_icon_url: null,
  authors: [],
  emotion_tags: [],
  interest_tags: [],
  albums: [],
  created_at: "2026-01-01T00:00:00Z",
};

const mockMusicDetail: MusicDetail = {
  id: 1,
  title: "Test Song",
  is_vip: false,
  source: null,
  style: null,
  language: null,
  collect_count: 0,
  hot: 0,
  comment_count: 0,
  play_count: 0,
  is_published: true,
  release_date: null,
  file_url: "https://example.com/1.mp3",
  lyrics_url: null,
  cover_icon_url: null,
  cover_home_url: null,
  cover_play_url: null,
  authors: [],
  instruments: [],
  emotion_tags: [],
  interest_tags: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("usePlayMusic", () => {
  const playStandalone = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePlayerStore).mockReturnValue(playStandalone);
  });

  it("calls getMusicDetail with the correct id for list items", async () => {
    vi.mocked(musicApi.getMusicDetail).mockResolvedValue(mockMusicDetail);

    const { result } = renderHook(() => usePlayMusic());
    await act(async () => {
      await result.current.playMusicListItem(mockMusicListItem);
    });

    expect(musicApi.getMusicDetail).toHaveBeenCalledWith(mockMusicListItem.id);
  });

  it("calls getMusicDetail with the correct id for direct play", async () => {
    vi.mocked(musicApi.getMusicDetail).mockResolvedValue(mockMusicDetail);

    const { result } = renderHook(() => usePlayMusic());
    await act(async () => {
      await result.current.playMusicById(mockMusicDetail.id);
    });

    expect(musicApi.getMusicDetail).toHaveBeenCalledWith(mockMusicDetail.id);
  });

  it("calls playStandalone when file_url is present", async () => {
    vi.mocked(musicApi.getMusicDetail).mockResolvedValue(mockMusicDetail);

    const { result } = renderHook(() => usePlayMusic());
    await act(async () => {
      await result.current.playMusicById(mockMusicDetail.id);
    });

    await waitFor(() => {
      expect(playStandalone).toHaveBeenCalledTimes(1);
    });
  });

  it("does not call playStandalone when file_url is missing", async () => {
    vi.mocked(musicApi.getMusicDetail).mockResolvedValue({
      ...mockMusicDetail,
      file_url: null,
    });

    const { result } = renderHook(() => usePlayMusic());
    await act(async () => {
      await result.current.playMusicById(mockMusicDetail.id);
    });

    expect(playStandalone).not.toHaveBeenCalled();
  });

  it("handles API errors silently in playMusicById", async () => {
    vi.mocked(musicApi.getMusicDetail).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => usePlayMusic());
    await expect(result.current.playMusicById(1)).resolves.toBeUndefined();
  });
});
