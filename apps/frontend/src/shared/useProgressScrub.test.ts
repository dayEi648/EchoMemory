import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useProgressScrub } from "./useProgressScrub";

describe("useProgressScrub", () => {
  it("does not seek while dragging; seeks immediately on release", () => {
    const seek = vi.fn();

    const { result } = renderHook(() =>
      useProgressScrub({
        progress: 20,
        currentTime: 60,
        duration: 300,
        seek,
        enabled: true,
      }),
    );

    const bar = document.createElement("div");
    bar.getBoundingClientRect = () =>
      ({
        left: 0,
        width: 200,
        top: 0,
        height: 20,
        right: 200,
        bottom: 20,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }) as DOMRect;
    result.current.barRef.current = bar;

    act(() => {
      result.current.handlePointerDown({
        clientX: 100,
        currentTarget: {
          setPointerCapture: vi.fn(),
        },
        pointerId: 1,
      } as unknown as React.PointerEvent<HTMLDivElement>);
    });

    expect(seek).not.toHaveBeenCalled();
    expect(result.current.displayProgress).toBe(50);

    act(() => {
      window.dispatchEvent(new Event("pointerup"));
    });

    expect(seek).toHaveBeenCalledTimes(1);
    expect(seek).toHaveBeenCalledWith(50);
  });
});
