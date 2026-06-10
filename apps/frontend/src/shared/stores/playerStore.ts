import { create } from "zustand";

import type { MusicListItem } from "../api/types";
import { createPlayHistoryApi } from "../api/playHistoryApi";
import { createLocalStorageTokenStore } from "../auth/tokenStore";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const playHistoryApi = createPlayHistoryApi({ baseUrl: API_BASE_URL, tokenStore });

/** 播放器中使用的可播放曲目，在 MusicListItem 基础上扩展 file_url */
export interface PlayerTrack extends MusicListItem {
  file_url: string | null;
}

interface PlayerState {
  currentTrack: PlayerTrack | null;
  queue: PlayerTrack[];
  queueIndex: number;
  isPlaying: boolean;
  progress: number;
  currentTime: number;
  duration: number;
  volume: number;
  isShuffle: boolean;
  isRepeat: boolean;
  recorded: boolean;

  playTrack: (track: PlayerTrack) => void;
  playQueue: (queue: PlayerTrack[], startIndex?: number) => void;
  togglePlay: () => void;
  next: () => void;
  prev: () => void;
  seek: (percent: number) => void;
  setVolume: (vol: number) => void;
  toggleShuffle: () => void;
  toggleRepeat: () => void;
}

const shouldRecordPlay = (currentTime: number, duration: number, recorded: boolean): boolean => {
  if (recorded) return false;
  if (duration <= 0) return false;
  if (currentTime >= 30) return true;
  if (currentTime / duration >= 0.5) return true;
  return false;
};

/** 模块级单例 Audio 实例，避免 Zustand store 重新初始化时创建多个实例。 */
const audio = new Audio();
audio.volume = 0.8;

/** 确保事件监听器只绑定一次，防止 Strict Mode / Fast Refresh 导致重复监听。 */
let _listenersBound = false;

export const usePlayerStore = create<PlayerState>((set, get) => {
  if (!_listenersBound) {
    _listenersBound = true;

    audio.addEventListener("timeupdate", () => {
      const state = get();
      const currentTime = audio.currentTime;
      const duration = audio.duration || 0;
      const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

      if (shouldRecordPlay(currentTime, duration, state.recorded) && state.currentTrack) {
        set({ recorded: true });
        playHistoryApi.recordPlay(state.currentTrack.id).catch(() => {
          // silently fail
        });
      }

      set({ currentTime, duration, progress });
    });

    audio.addEventListener("ended", () => {
      const state = get();
      if (state.isRepeat && state.currentTrack) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
      } else {
        state.next();
      }
    });

    audio.addEventListener("error", () => {
      set({ isPlaying: false });
    });

    audio.addEventListener("play", () => {
      set({ isPlaying: true });
    });

    audio.addEventListener("pause", () => {
      set({ isPlaying: false });
    });

    audio.addEventListener("loadedmetadata", () => {
      set({ duration: audio.duration || 0 });
    });
  }

  return {
    currentTrack: null,
    queue: [],
    queueIndex: 0,
    isPlaying: false,
    progress: 0,
    currentTime: 0,
    duration: 0,
    volume: 0.8,
    isShuffle: false,
    isRepeat: false,
    recorded: false,

    playTrack: (track) => {
      const state = get();
      if (state.currentTrack?.id === track.id) {
        state.togglePlay();
        return;
      }
      if (!track.file_url) {
        return;
      }
      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        currentTrack: track,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    playQueue: (queue, startIndex = 0) => {
      const track = queue[startIndex];
      if (!track || !track.file_url) return;
      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        queue,
        queueIndex: startIndex,
        currentTrack: track,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    togglePlay: () => {
      const { isPlaying, currentTrack } = get();
      if (isPlaying) {
        audio.pause();
      } else if (currentTrack) {
        audio.play().catch(() => {});
      }
    },

    next: () => {
      const { queue, queueIndex, isShuffle } = get();
      if (queue.length === 0) {
        set({ isPlaying: false, progress: 0, currentTime: 0 });
        return;
      }
      let nextIndex: number;
      if (isShuffle) {
        nextIndex = Math.floor(Math.random() * queue.length);
      } else {
        nextIndex = queueIndex + 1;
        if (nextIndex >= queue.length) nextIndex = 0;
      }
      const track = queue[nextIndex];
      if (!track.file_url) return;
      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        queueIndex: nextIndex,
        currentTrack: track,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    prev: () => {
      const { queue, queueIndex } = get();
      if (queue.length === 0) {
        set({ isPlaying: false, progress: 0, currentTime: 0 });
        return;
      }
      let prevIndex = queueIndex - 1;
      if (prevIndex < 0) prevIndex = queue.length - 1;
      const track = queue[prevIndex];
      if (!track.file_url) return;
      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        queueIndex: prevIndex,
        currentTrack: track,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    seek: (percent) => {
      const { duration } = get();
      if (duration > 0) {
        audio.currentTime = (percent / 100) * duration;
      }
    },

    setVolume: (vol) => {
      const clamped = Math.max(0, Math.min(1, vol));
      audio.volume = clamped;
      set({ volume: clamped });
    },

    toggleShuffle: () => {
      set((s) => ({ isShuffle: !s.isShuffle }));
    },

    toggleRepeat: () => {
      set((s) => ({ isRepeat: !s.isRepeat }));
    },
  };
});
