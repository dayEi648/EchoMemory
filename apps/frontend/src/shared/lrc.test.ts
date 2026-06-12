import { afterEach, describe, expect, it, vi } from "vitest";

import {
  animateScrollTop,
  computeLineTransitionDuration,
  computeLyricScrollTop,
  computeScrollTopForLineCenter,
  easeOutCubic,
  getActiveLyricIndex,
  getDisplayLyricIndex,
  getInterpolatedLyricIndex,
  LYRIC_LINE_TRANSITION_MS,
  parseLrc,
} from "./lrc";

describe("parseLrc", () => {
  it("parses standard LRC timestamps", () => {
    const { lines, synced } = parseLrc(`[00:12.50]第一句
[00:18.00]第二句`);
    expect(synced).toBe(true);
    expect(lines).toEqual([
      { time: 12.5, text: "第一句" },
      { time: 18, text: "第二句" },
    ]);
  });

  it("skips metadata tags", () => {
    const { lines, synced } = parseLrc(`[ti:Test Song]
[ar:Artist]
[00:01.00]歌词行`);
    expect(synced).toBe(true);
    expect(lines).toEqual([{ time: 1, text: "歌词行" }]);
  });

  it("falls back to plain text lines without timestamps", () => {
    const { lines, synced } = parseLrc("第一行\n第二行");
    expect(synced).toBe(false);
    expect(lines).toEqual([
      { time: 0, text: "第一行" },
      { time: 0, text: "第二行" },
    ]);
  });
});

describe("getInterpolatedLyricIndex", () => {
  const lines = parseLrc(`[00:10.00]A
[00:20.00]B`).lines;

  it("interpolates between two lines", () => {
    expect(getInterpolatedLyricIndex(lines, 10)).toBe(0);
    expect(getInterpolatedLyricIndex(lines, 15)).toBeCloseTo(0.5, 5);
    expect(getInterpolatedLyricIndex(lines, 20)).toBeCloseTo(1, 5);
  });
});

describe("computeLyricScrollTop", () => {
  it("centers the target line in the viewport", () => {
    const centers = [50, 100, 150];
    expect(computeLyricScrollTop(centers, 1, 200)).toBe(0);
    expect(computeLyricScrollTop(centers, 1, 100)).toBe(50);
  });
});

describe("lyric line transition helpers", () => {
  it("easeOutCubic ends at 1", () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
  });

  it("centers a line in the viewport", () => {
    expect(computeScrollTopForLineCenter(150, 200)).toBe(50);
  });

  it("uses standard duration for adjacent lines", () => {
    expect(computeLineTransitionDuration(1, 2)).toBe(LYRIC_LINE_TRANSITION_MS);
  });

  it("shortens duration when skipping multiple lines", () => {
    expect(computeLineTransitionDuration(0, 4)).toBeLessThan(LYRIC_LINE_TRANSITION_MS);
  });

  it("sets scrollTop immediately when duration is 0", () => {
    const scrollEl = document.createElement("div");
    let scrollTop = 0;
    Object.defineProperty(scrollEl, "scrollTop", {
      get: () => scrollTop,
      set: (value: number) => {
        scrollTop = value;
      },
    });

    animateScrollTop(scrollEl, 80, 0);
    expect(scrollTop).toBe(80);
  });

  it("animates scrollTop with eased rAF steps", () => {
    const scrollEl = document.createElement("div");
    let scrollTop = 0;
    Object.defineProperty(scrollEl, "scrollTop", {
      get: () => scrollTop,
      set: (value: number) => {
        scrollTop = value;
      },
    });

    let clock = 0;
    vi.spyOn(performance, "now").mockImplementation(() => clock);

    const rafCallbacks: FrameRequestCallback[] = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length;
    });

    animateScrollTop(scrollEl, 100, 100);
    expect(scrollTop).toBe(0);

    const runFrame = (time: number) => {
      const cb = rafCallbacks.at(-1);
      if (!cb) throw new Error("missing rAF callback");
      clock = time;
      cb(time);
    };

    runFrame(0);
    expect(scrollTop).toBe(0);

    runFrame(50);
    expect(scrollTop).toBeGreaterThan(0);
    expect(scrollTop).toBeLessThan(100);

    runFrame(100);
    expect(scrollTop).toBe(100);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getActiveLyricIndex", () => {
  const { lines } = parseLrc(`[00:10.00]A
[00:20.00]B
[00:30.00]C`);

  it("returns -1 before first line", () => {
    expect(getActiveLyricIndex(lines, 5)).toBe(-1);
  });

  it("returns correct index during playback", () => {
    expect(getActiveLyricIndex(lines, 10)).toBe(0);
    expect(getActiveLyricIndex(lines, 25)).toBe(1);
    expect(getActiveLyricIndex(lines, 30)).toBe(2);
  });
});

describe("getDisplayLyricIndex", () => {
  const { lines } = parseLrc(`[00:10.00]A
[00:20.00]B`);

  it("targets the first line before its timestamp", () => {
    expect(getDisplayLyricIndex(lines, 0)).toBe(0);
    expect(getDisplayLyricIndex(lines, 5)).toBe(0);
  });

  it("matches active index once playback reaches timestamps", () => {
    expect(getDisplayLyricIndex(lines, 10)).toBe(0);
    expect(getDisplayLyricIndex(lines, 20)).toBe(1);
  });
});
