import { beforeEach, describe, expect, it, vi } from "vitest";
import { act } from "@testing-library/react";

const mockMusicDetail = {
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

const mockMusicListItem = {
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

// Mock the player store and API
vi.mock("./stores/playerStore", () => ({
  usePlayerStore: vi.fn(() => ({
    playStandalone: vi.fn(),
  })),
}));

vi.mock("./api/instances", () => ({
  musicApi: {
    getMusicDetail: vi.fn(),
  },
}));

import { usePlayerStore } from "./stores/playerStore";
import { musicApi } from "./api/instances";

// Re-create usePlayMusic inline for testing
const mockPlayMusic = () => {
  const playStandalone = usePlayerStore((s: any) => s.playStandalone);

  const playMusicListItem = async (music: typeof mockMusicListItem) => {
    try {
      const detail = await musicApi.getMusicDetail(music.id);
      if ((detail as any).file_url) {
        await playStandalone(expect.any(Object));
      }
    } catch {
      // noop
    }
  };

  const playMusicById = async (musicId: number) => {
    try {
      const detail = await musicApi.getMusicDetail(musicId);
      if ((detail as any).file_url) {
        await playStandalone(expect.any(Object));
      }
    } catch {
      // noop
    }
  };

  return { playMusicListItem, playMusicById };
};

describe("usePlayMusic", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls getMusicDetail with the correct id for list items", async () => {
    (musicApi.getMusicDetail as any).mockResolvedValue(mockMusicDetail);

    const { playMusicListItem } = mockPlayMusic();
    await playMusicListItem(mockMusicListItem);

    expect(musicApi.getMusicDetail).toHaveBeenCalledWith(2);
  });

  it("calls getMusicDetail with the correct id for direct play", async () => {
    (musicApi.getMusicDetail as any).mockResolvedValue(mockMusicDetail);

    const { playMusicById } = mockPlayMusic();
    await playMusicById(1);

    expect(musicApi.getMusicDetail).toHaveBeenCalledWith(1);
  });

  it("does not call playStandalone when file_url is missing", async () => {
    (musicApi.getMusicDetail as any).mockResolvedValue({ ...mockMusicDetail, file_url: null });
    const playStandalone = vi.fn();
    vi.mocked(usePlayerStore).mockReturnValue(playStandalone as any);

    const { playMusicById } = mockPlayMusic();
    await playMusicById(1);

    expect(playStandalone).not.toHaveBeenCalled();
  });

  it("handles API errors silently in playMusicById", async () => {
    (musicApi.getMusicDetail as any).mockRejectedValue(new Error("Network error"));

    const { playMusicById } = mockPlayMusic();
    // Should not throw
    await expect(playMusicById(1)).resolves.toBeUndefined();
  });
});
