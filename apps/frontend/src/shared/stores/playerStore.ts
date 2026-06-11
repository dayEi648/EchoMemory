import { create } from "zustand";

import type { MusicListItem } from "../api/types";
import { createPlayHistoryApi } from "../api/playHistoryApi";
import { createMusicApi } from "../api/musicApi";
import { createLocalStorageTokenStore } from "../auth/tokenStore";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const playHistoryApi = createPlayHistoryApi({ baseUrl: API_BASE_URL, tokenStore });
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });

/** 播放器中使用的可播放曲目，在 MusicListItem 基础上扩展 file_url */
export interface PlayerTrack extends MusicListItem {
  file_url: string | null;
}

/** 描述当前播放队列的来源上下文 */
export type QueueContext =
  | { type: "playlist"; id: number; name: string }
  | { type: "album"; id: number; name: string }
  | { type: "history" }
  | null;

interface PlayerState {
  currentTrack: PlayerTrack | null;
  queue: PlayerTrack[];
  queueIndex: number;
  queueContext: QueueContext;
  isPlaying: boolean;
  progress: number;
  currentTime: number;
  duration: number;
  volume: number;
  isShuffle: boolean;
  isRepeat: boolean;
  recorded: boolean;

  /** 直接播放单曲（不改变队列上下文） */
  playTrack: (track: PlayerTrack) => void;
  /** 以指定队列上下文播放（专辑/歌单/历史等） */
  playInContext: (
    track: PlayerTrack,
    contextTracks: PlayerTrack[],
    context: NonNullable<QueueContext>,
  ) => void;
  /** 独立播放模式：自动将当前歌曲 + 播放历史拼接为队列 */
  playStandalone: (track: PlayerTrack) => Promise<void>;
  /** 设置队列并开始播放（底层方法） */
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

  /** 底层：切换到指定队列中的指定索引并播放 */
  const _switchToTrack = (queue: PlayerTrack[], index: number) => {
    const track = queue[index];
    if (!track || !track.file_url) return false;
    audio.src = track.file_url;
    audio.load();
    audio.play().catch(() => {});
    set({
      queue,
      queueIndex: index,
      currentTrack: track,
      isPlaying: true,
      progress: 0,
      currentTime: 0,
      duration: 0,
      recorded: false,
    });
    return true;
  };

  /** 懒加载获取 track 的 file_url */
  const _ensureFileUrl = async (track: PlayerTrack): Promise<PlayerTrack | null> => {
    if (track.file_url) return track;
    try {
      const detail = await musicApi.getMusicDetail(track.id);
      if (detail.file_url) {
        const updated: PlayerTrack = { ...track, file_url: detail.file_url };
        // 更新队列中的引用
        const { queue } = get();
        const idx = queue.findIndex((t) => t.id === track.id);
        if (idx >= 0) {
          const newQueue = [...queue];
          newQueue[idx] = updated;
          set({ queue: newQueue });
        }
        return updated;
      }
      return null;
    } catch {
      return null;
    }
  };

  /** 跳到队列中的下一首（支持懒加载 file_url） */
  const _advance = async (direction: 1 | -1) => {
    const { queue, queueIndex, isShuffle } = get();
    if (queue.length === 0) {
      set({ isPlaying: false, progress: 0, currentTime: 0 });
      return;
    }

    let nextIndex: number;
    if (isShuffle) {
      nextIndex = Math.floor(Math.random() * queue.length);
    } else {
      nextIndex = queueIndex + direction;
      if (nextIndex >= queue.length) nextIndex = 0;
      if (nextIndex < 0) nextIndex = queue.length - 1;
    }

    // 尝试播放，最多尝试队列长度次（防止死循环）
    for (let attempt = 0; attempt < queue.length; attempt++) {
      let track = queue[nextIndex];
      if (!track.file_url) {
        track = (await _ensureFileUrl(track)) ?? track;
      }
      if (track.file_url) {
        _switchToTrack(get().queue, nextIndex);
        return;
      }
      // 跳过无 file_url 的歌曲，继续找下一首
      if (isShuffle) {
        nextIndex = Math.floor(Math.random() * queue.length);
      } else {
        nextIndex = nextIndex + direction;
        if (nextIndex >= queue.length) nextIndex = 0;
        if (nextIndex < 0) nextIndex = queue.length - 1;
      }
    }

    // 所有歌曲都无法播放
    set({ isPlaying: false });
  };

  return {
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
        queueContext: null,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    playInContext: (track, contextTracks, context) => {
      if (!track.file_url) return;

      // 找到 track 在上下文中的索引
      const idx = contextTracks.findIndex((t) => t.id === track.id);
      const startIndex = idx >= 0 ? idx : 0;

      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        queue: contextTracks,
        queueIndex: startIndex,
        queueContext: context,
        currentTrack: track,
        isPlaying: true,
        progress: 0,
        currentTime: 0,
        duration: 0,
        recorded: false,
      });
    },

    playStandalone: async (track) => {
      if (!track.file_url) return;

      // 获取最近播放历史
      let historyTracks: PlayerTrack[] = [];
      try {
        const history = await playHistoryApi.listPlayHistory({ limit: 50 });
        historyTracks = history.items
          .filter((h) => h.music.id !== track.id)
          .map(
            (h): PlayerTrack => ({
              id: h.music.id,
              title: h.music.title,
              is_vip: false,
              hot: 0,
              play_count: 0,
              cover_icon_url: h.music.cover_icon_url,
              authors: [],
              emotion_tags: [],
              interest_tags: [],
              albums: [],
              created_at: "",
              file_url: null, // 懒加载
            }),
          );
      } catch {
        // 获取历史失败也不影响播放
      }

      const queue = [track, ...historyTracks];
      audio.src = track.file_url;
      audio.load();
      audio.play().catch(() => {});
      set({
        queue,
        queueIndex: 0,
        queueContext: { type: "history" },
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
        queueContext: null,
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
      void _advance(1);
    },

    prev: () => {
      void _advance(-1);
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
