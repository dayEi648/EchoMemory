import { useCallback, useEffect, useRef, useState } from "react";

interface UseProgressScrubOptions {
  progress: number;
  currentTime: number;
  duration: number;
  seek: (percent: number) => void;
  /** 为 false 时不响应拖动 */
  enabled?: boolean;
}

/**
 * 进度条拖动交互：拖动期间仅更新 UI 预览、音频继续播放；松手后立即 seek。
 */
export function useProgressScrub({
  progress,
  currentTime,
  duration,
  seek,
  enabled = true,
}: UseProgressScrubOptions) {
  const [isDragging, setIsDragging] = useState(false);
  const [dragPercent, setDragPercent] = useState(0);
  const barRef = useRef<HTMLDivElement>(null);
  const dragPercentRef = useRef(0);

  const percentFromClientX = useCallback(
    (clientX: number): number | null => {
      if (!barRef.current || duration <= 0 || !enabled) return null;
      const rect = barRef.current.getBoundingClientRect();
      if (rect.width <= 0) return null;
      return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
    },
    [duration, enabled],
  );

  const updateDragPercent = useCallback((percent: number) => {
    dragPercentRef.current = percent;
    setDragPercent(percent);
  }, []);

  const commitSeek = useCallback(() => {
    seek(dragPercentRef.current);
  }, [seek]);

  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (!enabled) return;
      const percent = percentFromClientX(e.clientX);
      if (percent === null) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      setIsDragging(true);
      updateDragPercent(percent);
    },
    [enabled, percentFromClientX, updateDragPercent],
  );

  useEffect(() => {
    if (!isDragging) return;

    const onMove = (e: PointerEvent) => {
      if (e.buttons === 0) {
        setIsDragging(false);
        commitSeek();
        return;
      }
      const percent = percentFromClientX(e.clientX);
      if (percent !== null) updateDragPercent(percent);
    };

    const onUp = () => {
      setIsDragging(false);
      commitSeek();
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [isDragging, percentFromClientX, updateDragPercent, commitSeek]);

  const displayProgress = isDragging ? dragPercent : progress;
  const displayCurrentTime =
    isDragging && duration > 0 ? (dragPercent / 100) * duration : currentTime;

  return {
    barRef,
    isDragging,
    displayProgress,
    displayCurrentTime,
    handlePointerDown,
  };
}
