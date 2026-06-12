/** 单行歌词（LRC 时间戳 + 文本） */
export interface LyricLine {
  time: number;
  text: string;
}

export interface ParsedLrc {
  lines: LyricLine[];
  /** 是否含可同步的时间戳 */
  synced: boolean;
}

const LRC_TIME_PATTERN = /\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g;
const LRC_META_PATTERN = /^\[(ti|ar|al|by|offset|id|ve|re|au):/i;

/**
 * 将 LRC 毫秒/百分秒片段转为秒。
 */
function parseLrcFraction(fraction: string | undefined): number {
  if (!fraction) return 0;
  const normalized = fraction.padEnd(3, "0").slice(0, 3);
  return Number(normalized) / 1000;
}

/**
 * 解析 LRC 歌词文本为按时间排序的歌词行列表。
 * 支持元数据行过滤；无时间戳时按纯文本分行展示（不同步）。
 */
export function parseLrc(content: string): ParsedLrc {
  const lines: LyricLine[] = [];
  const plainLines: string[] = [];

  for (const rawLine of content.split(/\r?\n/)) {
    const trimmed = rawLine.trim().replace(/^\uFEFF/, "");
    if (!trimmed) continue;
    if (LRC_META_PATTERN.test(trimmed)) continue;

    const timestamps = [...trimmed.matchAll(LRC_TIME_PATTERN)];
    const text = trimmed.replace(LRC_TIME_PATTERN, "").trim();
    if (!text) continue;

    if (timestamps.length === 0) {
      plainLines.push(text);
      continue;
    }

    for (const match of timestamps) {
      const minutes = Number(match[1]);
      const seconds = Number(match[2]);
      const fraction = parseLrcFraction(match[3]);
      lines.push({
        time: minutes * 60 + seconds + fraction,
        text,
      });
    }
  }

  if (lines.length > 0) {
    lines.sort((a, b) => a.time - b.time);
    return { lines, synced: true };
  }

  if (plainLines.length > 0) {
    return {
      lines: plainLines.map((text) => ({ time: 0, text })),
      synced: false,
    };
  }

  return { lines: [], synced: false };
}

/**
 * 根据当前播放时间获取应高亮的歌词行索引。
 */
export function getActiveLyricIndex(lines: LyricLine[], currentTime: number): number {
  if (lines.length === 0 || currentTime < 0) return -1;

  let index = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].time <= currentTime + 0.05) {
      index = i;
    } else {
      break;
    }
  }
  return index;
}

/**
 * 获取界面展示用的歌词行索引。
 * 播放尚未到达第一句时间戳时，仍对准第一句（提前就位）。
 */
export function getDisplayLyricIndex(lines: LyricLine[], currentTime: number): number {
  if (lines.length === 0 || currentTime < 0) return -1;
  const active = getActiveLyricIndex(lines, currentTime);
  return active >= 0 ? active : 0;
}

/**
 * 在两行歌词时间戳之间插值，得到小数行索引（用于连续滚动）。
 */
export function getInterpolatedLyricIndex(lines: LyricLine[], currentTime: number): number {
  if (lines.length === 0) return -1;

  const active = getActiveLyricIndex(lines, currentTime);
  if (active < 0) return 0;
  if (active >= lines.length - 1) return active;

  const t0 = lines[active].time;
  const t1 = lines[active + 1].time;
  const span = t1 - t0;
  if (span <= 0.001) return active;

  const progress = Math.max(0, Math.min(1, (currentTime - t0) / span));
  return active + progress;
}

/**
 * 根据插值行索引计算应滚动到的 scrollTop，使对应行位于视口正中。
 */
export function computeLyricScrollTop(
  lineCenters: number[],
  fractionalIndex: number,
  viewportHeight: number,
): number {
  if (lineCenters.length === 0 || fractionalIndex < 0 || viewportHeight <= 0) return 0;

  const clamped = Math.max(0, Math.min(fractionalIndex, lineCenters.length - 1));
  const i = Math.floor(clamped);
  const frac = clamped - i;
  const next = Math.min(i + 1, lineCenters.length - 1);
  const centerY = lineCenters[i] + (lineCenters[next] - lineCenters[i]) * frac;
  return Math.max(0, centerY - viewportHeight / 2);
}

/** 歌词自动跟随时使用的平滑系数（越大越快贴近目标） */
export const LYRIC_SCROLL_LERP = 0.14;

/** 相邻歌词行切换时，滚动动画的标准时长（毫秒）。与播放进度无关。 */
export const LYRIC_LINE_TRANSITION_MS = 520;

/** 跨多行跳转时允许缩短的最短动画时长（毫秒） */
export const LYRIC_LINE_TRANSITION_MIN_MS = 320;

/**
 * ease-out 三次曲线：起步快、收尾柔，常用于歌词行间过渡。
 */
export function easeOutCubic(t: number): number {
  const clamped = Math.max(0, Math.min(1, t));
  return 1 - (1 - clamped) ** 3;
}

/**
 * 计算使一行歌词垂直居中所需的 scrollTop。
 */
export function computeScrollTopForLineCenter(
  lineCenterY: number,
  viewportHeight: number,
): number {
  if (viewportHeight <= 0) return 0;
  return Math.max(0, lineCenterY - viewportHeight / 2);
}

/**
 * 根据起止行索引决定动画时长：相邻行用标准时长，跨行跳转略快但仍保持过渡感。
 */
export function computeLineTransitionDuration(
  fromIndex: number,
  toIndex: number,
  standardMs: number = LYRIC_LINE_TRANSITION_MS,
): number {
  const steps = Math.abs(toIndex - fromIndex);
  if (steps <= 1) return standardMs;
  return Math.max(LYRIC_LINE_TRANSITION_MIN_MS, standardMs - (steps - 1) * 45);
}

export interface ScrollTopAnimationHandle {
  cancel: () => void;
}

/**
 * 将滚动容器平滑移动到目标 scrollTop（固定时长 + 缓动），返回可取消句柄。
 */
export function animateScrollTop(
  scrollEl: HTMLElement,
  targetTop: number,
  durationMs: number,
): ScrollTopAnimationHandle {
  let rafId = 0;
  let cancelled = false;
  const startTop = scrollEl.scrollTop;
  const distance = targetTop - startTop;

  if (Math.abs(distance) < 0.5 || durationMs <= 0) {
    scrollEl.scrollTop = targetTop;
    return { cancel: () => {} };
  }

  const startTime = performance.now();

  const tick = (now: number) => {
    if (cancelled) return;
    const t = Math.min(1, (now - startTime) / durationMs);
    scrollEl.scrollTop = startTop + distance * easeOutCubic(t);
    if (t < 1) {
      rafId = requestAnimationFrame(tick);
    }
  };

  rafId = requestAnimationFrame(tick);

  return {
    cancel: () => {
      cancelled = true;
      if (rafId) cancelAnimationFrame(rafId);
    },
  };
}
