import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { FileText, LocateFixed } from "lucide-react";

import { musicApi } from "../../shared/api/instances";
import { usePlayerStore } from "../../shared/stores/playerStore";
import {
  computeLineTransitionDuration,
  getDisplayLyricIndex,
  LYRIC_LINE_TRANSITION_MS,
  parseLrc,
  type LyricLine,
} from "../../shared/lrc";

interface PlayerScreenLyricsProps {
  musicId: number;
  hasLyrics: boolean;
}

function lyricLineClass(activeIndex: number, index: number): string {
  if (activeIndex < 0) return "";
  if (index === activeIndex) return "ps-lyric-row--current";
  if (index < activeIndex) return "ps-lyric-row--past";
  return "ps-lyric-row--upcoming";
}

/**
 * 播放页歌词：自动跟拍用 CSS transform 过渡。
 * 用户手动浏览时切换为原生 scroll。
 *
 * 性能优化：使用 rAF 节流计算 activeIndex，仅在索引变化时触发重渲染和自动跟随，
 * 避免每帧 ~60 次的无效 React 调度。
 */
export const PlayerScreenLyrics = ({ musicId, hasLyrics }: PlayerScreenLyricsProps) => {
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id);
  const duration = usePlayerStore((s) => s.duration);
  const seek = usePlayerStore((s) => s.seek);
  const isActiveTrack = currentTrackId === musicId;

  const [lines, setLines] = useState<LyricLine[]>([]);
  const [synced, setSynced] = useState(true);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [userLocked, setUserLocked] = useState(false);
  const [translateY, setTranslateY] = useState(0);
  const [transitionMs, setTransitionMs] = useState(0);
  const [activeIndex, setActiveIndex] = useState(-1);

  const scrollRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const lineRefs = useRef<(HTMLParagraphElement | null)[]>([]);
  const userLockedRef = useRef(false);
  const prevActiveIndexRef = useRef(-1);
  const activeIndexRef = useRef(-1);
  const translateYRef = useRef(0);
  const rafIdRef = useRef(0);

  // rAF 节流：仅在 activeIndex 实际变化时更新 state
  useEffect(() => {
    if (!isActiveTrack || !synced || lines.length === 0) {
      setActiveIndex(-1);
      return;
    }

    const tick = () => {
      const ct = usePlayerStore.getState().currentTime;
      const idx = getDisplayLyricIndex(lines, ct);
      setActiveIndex((prev) => {
        if (prev !== idx) {
          activeIndexRef.current = idx;
          return idx;
        }
        return prev;
      });
      rafIdRef.current = requestAnimationFrame(tick);
    };
    rafIdRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafIdRef.current);
  }, [isActiveTrack, synced, lines]);

  activeIndexRef.current = activeIndex;
  translateYRef.current = translateY;
  userLockedRef.current = userLocked;

  const computeTranslateY = useCallback((index: number): number => {
    const scrollEl = scrollRef.current;
    const lineEl = lineRefs.current[index];
    if (!scrollEl || !lineEl || scrollEl.clientHeight <= 0) return 0;
    const lineCenter = lineEl.offsetTop + lineEl.offsetHeight / 2;
    return scrollEl.clientHeight / 2 - lineCenter;
  }, []);

  const syncScrollPadding = useCallback(() => {
    const scrollEl = scrollRef.current;
    const inner = innerRef.current;
    if (!scrollEl || !inner) return;
    const half = scrollEl.clientHeight / 2;
    inner.style.paddingTop = `${half}px`;
    inner.style.paddingBottom = `${half}px`;
  }, []);

  const applyAutoFollow = useCallback(
    (
      index: number,
      options: { animate?: boolean; fromIndex?: number; forceAnimate?: boolean } = {},
    ): boolean => {
      if (index < 0) return false;

      const scrollEl = scrollRef.current;
      const lineEl = lineRefs.current[index];
      if (!scrollEl || !lineEl || scrollEl.clientHeight <= 0) {
        return false;
      }

      const fromIndex = options.fromIndex ?? prevActiveIndexRef.current;
      const shouldAnimate =
        options.forceAnimate === true ||
        (options.animate !== false && fromIndex >= 0 && fromIndex !== index);
      const duration = shouldAnimate
        ? options.forceAnimate
          ? LYRIC_LINE_TRANSITION_MS
          : computeLineTransitionDuration(fromIndex, index)
        : 0;

      setTransitionMs(duration);
      setTranslateY(computeTranslateY(index));
      prevActiveIndexRef.current = index;
      return true;
    },
    [computeTranslateY],
  );

  const enterManualScroll = useCallback(() => {
    const scrollEl = scrollRef.current;
    if (!scrollEl || userLockedRef.current) return;

    userLockedRef.current = true;
    setUserLocked(true);
    setTransitionMs(0);

    const preservedTop = Math.max(0, -translateYRef.current);
    setTranslateY(0);
    scrollEl.scrollTop = preservedTop;
  }, []);

  const loadLyrics = useCallback(async () => {
    if (!hasLyrics) {
      setLines([]);
      setSynced(true);
      setLoadError(false);
      return;
    }
    setLoading(true);
    setLoadError(false);
    try {
      const { content } = await musicApi.getMusicLyrics(musicId);
      const parsed = parseLrc(content);
      setLines(parsed.lines);
      setSynced(parsed.synced);
      setLoadError(parsed.lines.length === 0);
    } catch {
      setLines([]);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [hasLyrics, musicId]);

  useEffect(() => {
    void loadLyrics();
  }, [loadLyrics]);

  useEffect(() => {
    userLockedRef.current = false;
    setUserLocked(false);
    prevActiveIndexRef.current = -1;
    setTranslateY(0);
    setTransitionMs(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [musicId]);

  useEffect(() => {
    const scrollEl = scrollRef.current;
    if (!scrollEl || lines.length === 0) return;

    syncScrollPadding();

    const observer = new ResizeObserver(() => {
      syncScrollPadding();
      if (!userLockedRef.current && activeIndexRef.current >= 0) {
        applyAutoFollow(activeIndexRef.current, { animate: false });
      }
    });
    observer.observe(scrollEl);
    return () => observer.disconnect();
  }, [lines, syncScrollPadding, applyAutoFollow]);

  useEffect(() => {
    const scrollEl = scrollRef.current;
    if (!scrollEl) return;

    const onWheel = () => enterManualScroll();
    const onTouchStart = () => enterManualScroll();

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target;
      if (target instanceof Element && target.closest(".ps-lyric-row--seekable")) return;
      enterManualScroll();
    };

    scrollEl.addEventListener("wheel", onWheel, { passive: true });
    scrollEl.addEventListener("touchstart", onTouchStart, { passive: true });
    scrollEl.addEventListener("pointerdown", onPointerDown, { passive: true });

    return () => {
      scrollEl.removeEventListener("wheel", onWheel);
      scrollEl.removeEventListener("touchstart", onTouchStart);
      scrollEl.removeEventListener("pointerdown", onPointerDown);
    };
  }, [enterManualScroll, lines.length]);

  useLayoutEffect(() => {
    if (!isActiveTrack || !synced || userLocked || activeIndex < 0 || lines.length === 0 || loading) {
      return;
    }

    const fromIndex = prevActiveIndexRef.current;
    const indexChanged = activeIndex !== fromIndex;
    const needsInitialCenter = fromIndex < 0 || Math.abs(translateYRef.current) < 0.5;

    if (!indexChanged && !needsInitialCenter) return;

    applyAutoFollow(activeIndex, {
      animate: indexChanged && fromIndex >= 0,
      fromIndex,
    });
  }, [
    activeIndex,
    isActiveTrack,
    synced,
    userLocked,
    lines.length,
    loading,
    applyAutoFollow,
  ]);

  const handleUserScroll = () => {
    if (!userLockedRef.current) enterManualScroll();
  };

  const handleResync = () => {
    const scrollEl = scrollRef.current;
    if (scrollEl) scrollEl.scrollTop = 0;

    userLockedRef.current = false;
    setUserLocked(false);
    prevActiveIndexRef.current = -1;

    if (activeIndex >= 0) {
      applyAutoFollow(activeIndex, { forceAnimate: true });
    }
  };

  const handleLineClick = (line: LyricLine) => {
    if (!isActiveTrack || !synced || duration <= 0) return;
    userLockedRef.current = false;
    setUserLocked(false);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
    seek((line.time / duration) * 100);
  };

  if (!hasLyrics) {
    return (
      <div className="ps-lyrics ps-lyrics--empty">
        <FileText size={28} strokeWidth={1.25} />
        <p>暂无歌词</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="ps-lyrics ps-lyrics--empty">
        <div className="ps-lyrics__spinner" aria-hidden />
        <p>歌词加载中…</p>
      </div>
    );
  }

  if (loadError || lines.length === 0) {
    return (
      <div className="ps-lyrics ps-lyrics--empty">
        <FileText size={28} strokeWidth={1.25} />
        <p>歌词加载失败</p>
        <button className="ps-lyrics__retry" type="button" onClick={() => void loadLyrics()}>
          重试
        </button>
      </div>
    );
  }

  const listStyle: CSSProperties | undefined = userLocked
    ? undefined
    : {
        transform: `translateY(${translateY}px)`,
        transition:
          transitionMs > 0
            ? `transform ${transitionMs}ms cubic-bezier(0.22, 1, 0.36, 1)`
            : "none",
      };

  return (
    <div className="ps-lyrics" aria-label="歌词">
      {!isActiveTrack && synced && (
        <p className="ps-lyrics__hint">播放当前歌曲后，歌词将自动同步</p>
      )}

      {userLocked && isActiveTrack && synced && (
        <button className="ps-lyrics__resync" type="button" onClick={handleResync}>
          <LocateFixed size={15} />
          回到当前播放
        </button>
      )}

      <div
        ref={scrollRef}
        className={`ps-lyrics__scroll${userLocked ? " ps-lyrics__scroll--manual" : " ps-lyrics__scroll--auto"}`}
        onScroll={handleUserScroll}
      >
        <div ref={innerRef} className="ps-lyrics__list" style={listStyle}>
          {lines.map((line, index) => {
            const canSeek = isActiveTrack && synced && duration > 0;
            return (
              <p
                key={`${line.time}-${index}-${line.text}`}
                ref={(el) => {
                  lineRefs.current[index] = el;
                }}
                className={`ps-lyric-row ${lyricLineClass(activeIndex, index)}${canSeek ? " ps-lyric-row--seekable" : ""}`}
                onClick={() => handleLineClick(line)}
                role={canSeek ? "button" : undefined}
                tabIndex={canSeek ? 0 : undefined}
                onKeyDown={(e) => {
                  if (canSeek && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    handleLineClick(line);
                  }
                }}
              >
                {line.text}
              </p>
            );
          })}
        </div>
      </div>
    </div>
  );
};
