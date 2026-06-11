import { describe, expect, it } from "vitest";

import { toPlayerTrack, toPlayerTrackFromAlbumMusic, toPlayerTrackFromListItem } from "./utils";

describe("player track converters", () => {
  it("converts list items with null file_url", () => {
    const track = toPlayerTrackFromListItem(
      {
        id: 1,
        title: "Song",
        is_vip: false,
        hot: 0,
        play_count: 0,
        cover_icon_url: null,
        authors: [],
        created_at: "2026-06-11T00:00:00Z",
      },
      null,
    );
    expect(track.file_url).toBeNull();
    expect(track.emotion_tags).toEqual([]);
  });

  it("converts album music with missing tags", () => {
    const track = toPlayerTrackFromAlbumMusic(
      {
        id: 2,
        title: "Album Song",
        is_vip: false,
        hot: 1,
        play_count: 3,
        cover_icon_url: null,
        ordinal: 0,
      },
      [],
      "https://example.com/2.mp3",
      "2026-06-11T00:00:00Z",
    );
    expect(track.authors).toEqual([]);
    expect(track.file_url).toBe("https://example.com/2.mp3");
  });

  it("converts music detail", () => {
    const track = toPlayerTrack({
      id: 3,
      title: "Detail Song",
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
      file_url: "https://example.com/3.mp3",
      lyrics_url: null,
      cover_icon_url: null,
      cover_home_url: null,
      cover_play_url: null,
      authors: [],
      instruments: [],
      emotion_tags: [],
      interest_tags: [],
      created_at: "2026-06-11T00:00:00Z",
      updated_at: "2026-06-11T00:00:00Z",
    });
    expect(track.file_url).toBe("https://example.com/3.mp3");
  });
});
