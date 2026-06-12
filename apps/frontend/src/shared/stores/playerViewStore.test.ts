import { beforeEach, describe, expect, it } from "vitest";

import { usePlayerStore } from "./playerStore";
import { usePlayerViewStore } from "./playerViewStore";

describe("playerViewStore", () => {
  beforeEach(() => {
    usePlayerViewStore.setState({ isOpen: false, musicId: null });
    usePlayerStore.setState({ currentTrack: null });
  });

  it("opens overlay for a specific music id", () => {
    usePlayerViewStore.getState().open(42);
    const { isOpen, musicId } = usePlayerViewStore.getState();
    expect(isOpen).toBe(true);
    expect(musicId).toBe(42);
  });

  it("openCurrent uses the active track id", () => {
    usePlayerStore.setState({
      currentTrack: {
        id: 7,
        title: "Track",
        file_url: "https://example.com/a.mp3",
        cover_icon_url: null,
        authors: [],
        is_vip: false,
        hot: 0,
        play_count: 0,
        emotion_tags: [],
        interest_tags: [],
        albums: [],
        created_at: "2026-01-01T00:00:00Z",
      },
    });

    usePlayerViewStore.getState().openCurrent();
    expect(usePlayerViewStore.getState().musicId).toBe(7);
    expect(usePlayerViewStore.getState().isOpen).toBe(true);
  });

  it("openCurrent does nothing without a current track", () => {
    usePlayerViewStore.getState().openCurrent();
    expect(usePlayerViewStore.getState().isOpen).toBe(false);
  });

  it("close resets overlay state", () => {
    usePlayerViewStore.getState().open(1);
    usePlayerViewStore.getState().close();
    const { isOpen, musicId } = usePlayerViewStore.getState();
    expect(isOpen).toBe(false);
    expect(musicId).toBeNull();
  });
});
