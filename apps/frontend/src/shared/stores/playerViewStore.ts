import { create } from "zustand";

import { usePlayerStore } from "./playerStore";

interface PlayerViewState {
  isOpen: boolean;
  musicId: number | null;
  /** 打开指定歌曲的全屏播放页 */
  open: (musicId: number) => void;
  /** 打开当前正在播放的歌曲；无曲目时不执行 */
  openCurrent: () => void;
  close: () => void;
}

export const usePlayerViewStore = create<PlayerViewState>((set) => ({
  isOpen: false,
  musicId: null,
  open: (musicId) => set({ isOpen: true, musicId }),
  openCurrent: () => {
    const track = usePlayerStore.getState().currentTrack;
    if (track) {
      set({ isOpen: true, musicId: track.id });
    }
  },
  close: () => set({ isOpen: false, musicId: null }),
}));
