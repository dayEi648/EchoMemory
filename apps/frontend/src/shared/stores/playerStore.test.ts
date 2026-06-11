import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePlayerStore, type PlayerTrack } from "./playerStore";

const makeTrack = (id: number, title = `Song ${id}`): PlayerTrack => ({
  id,
  title,
  is_vip: false,
  hot: 0,
  play_count: 0,
  cover_icon_url: null,
  authors: [],
  emotion_tags: [],
  interest_tags: [],
  albums: [],
  created_at: "2026-06-11T00:00:00Z",
  file_url: `https://example.com/${id}.mp3`,
});

describe("playerStore queue semantics", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    usePlayerStore.setState({
      currentTrack: null,
      queue: [],
      queueIndex: 0,
      queueContext: null,
      isPlaying: false,
      progress: 0,
      currentTime: 0,
      duration: 0,
      volume: 0.8,
      isShuffle: false,
      isRepeat: false,
      recorded: false,
    });
  });

  it("accumulates standalone plays in a temporary playback queue", async () => {
    await usePlayerStore.getState().playStandalone(makeTrack(1, "First"));
    await usePlayerStore.getState().playStandalone(makeTrack(2, "Second"));

    const state = usePlayerStore.getState();
    expect(state.queueContext).toEqual({ type: "temporary" });
    expect(state.queue.map((track) => track.title)).toEqual(["First", "Second"]);
    expect(state.currentTrack?.title).toBe("Second");
    expect(state.queueIndex).toBe(1);
  });

  it("starts a fresh temporary queue after contextual playback", async () => {
    usePlayerStore.getState().playInContext(makeTrack(1, "Album Song"), [makeTrack(1, "Album Song")], {
      type: "album",
      id: 10,
      name: "Album",
    });

    await usePlayerStore.getState().playStandalone(makeTrack(2, "Loose Song"));

    const state = usePlayerStore.getState();
    expect(state.queueContext).toEqual({ type: "temporary" });
    expect(state.queue.map((track) => track.title)).toEqual(["Loose Song"]);
    expect(state.queueIndex).toBe(0);
  });
});
