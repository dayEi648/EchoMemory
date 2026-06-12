import { create } from "zustand";

import type { MusicListItem } from "../api/types";
import { getApis } from "../api/instances";
import { defaultPlayerController } from "./playerController";

/** 播放器中使用的可播放曲目，在 MusicListItem 基础上扩展 file_url */
export interface PlayerTrack extends MusicListItem {
  file_url: string | null;
}

/** 描述当前播放队列的来源上下文 */
export type QueueContext =
  | { type: "playlist"; id: number; name: string }
  | { type: "album"; id: number; name: string }
  | { type: "history" }
  | { type: "temporary" }
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
  /** 独立播放模式：将单曲加入当前临时播放列表 */
  playStandalone: (track: PlayerTrack) => void;
  /** 设置队列并开始播放（底层方法） */
  playQueue: (queue: PlayerTrack[], startIndex?: number, context?: QueueContext) => void;
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

const playerController = defaultPlayerController;
const audio = playerController.audio;

export const usePlayerStore = create<PlayerState>((set, get) => {
  playerController.bind({
    onTimeUpdate: (currentTime, duration) => {
      const state = get();
      const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

      if (shouldRecordPlay(currentTime, duration, state.recorded) && state.currentTrack) {
        set({ recorded: true });
        getApis().playHistoryApi.recordPlay(state.currentTrack.id).catch(() => {
          // silently fail
        });
      }

      set({ currentTime, duration, progress });
    },
    onEnded: () => {
      const state = get();
      if (state.isRepeat && state.currentTrack) {
        audio.currentTime = 0;
        audio.play().catch(() => {});
      } else {
        state.next();
      }
    },
    onError: () => {
      set({ isPlaying: false });
    },
    onPlay: () => {
      set({ isPlaying: true });
    },
    onPause: () => {
      set({ isPlaying: false });
    },
    onLoadedMetadata: (duration) => {
      set({ duration });
    },
  });

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
      const detail = await getApis().musicApi.getMusicDetail(track.id);
      if (detail.file_url) {
        const updated: PlayerTrack = { ...track, file_url: detail.file_url };
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

  /** 将单独播放的歌曲加入临时播放列表并切换到该歌曲 */
  const _playTemporaryTrack = (track: PlayerTrack) => {
    if (!track.file_url) return;

    const { queue, queueContext } = get();
    const baseQueue = queueContext?.type === "temporary" ? queue : [];
    const existingIndex = baseQueue.findIndex((item) => item.id === track.id);
    const nextQueue = existingIndex >= 0 ? [...baseQueue] : [...baseQueue, track];
    const startIndex = existingIndex >= 0 ? existingIndex : nextQueue.length - 1;

    if (existingIndex >= 0) {
      nextQueue[existingIndex] = track;
    }

    audio.src = track.file_url;
    audio.load();
    audio.play().catch(() => {});
    set({
      queue: nextQueue,
      queueIndex: startIndex,
      queueContext: { type: "temporary" },
      currentTrack: track,
      isPlaying: true,
      progress: 0,
      currentTime: 0,
      duration: 0,
      recorded: false,
    });
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

    for (let attempt = 0; attempt < queue.length; attempt++) {
      let track = queue[nextIndex];
      if (!track.file_url) {
        track = (await _ensureFileUrl(track)) ?? track;
      }
      if (track.file_url) {
        _switchToTrack(get().queue, nextIndex);
        return;
      }
      if (isShuffle) {
        nextIndex = Math.floor(Math.random() * queue.length);
      } else {
        nextIndex = nextIndex + direction;
        if (nextIndex >= queue.length) nextIndex = 0;
        if (nextIndex < 0) nextIndex = queue.length - 1;
      }
    }

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
      _playTemporaryTrack(track);
    },

    playInContext: (track, contextTracks, context) => {
      void (async () => {
        let resolved = track;
        if (!resolved.file_url) {
          const loaded = await _ensureFileUrl(resolved);
          if (loaded?.file_url) resolved = loaded;
        }
        if (!resolved.file_url) return;

        const idx = contextTracks.findIndex((t) => t.id === resolved.id);
        const startIndex = idx >= 0 ? idx : 0;

        audio.src = resolved.file_url;
        audio.load();
        audio.play().catch(() => {});
        set({
          queue: contextTracks.map((t) => (t.id === resolved.id ? resolved : t)),
          queueIndex: startIndex,
          queueContext: context,
          currentTrack: resolved,
          isPlaying: true,
          progress: 0,
          currentTime: 0,
          duration: 0,
          recorded: false,
        });
      })();
    },

    playStandalone: (track) => {
      _playTemporaryTrack(track);
    },

    playQueue: (queue, startIndex = 0, context = null) => {
      void (async () => {
        if (queue.length === 0) return;
        set({ queue, queueContext: context });

        let index = Math.max(0, Math.min(startIndex, queue.length - 1));
        for (let attempt = 0; attempt < queue.length; attempt++) {
          let track = get().queue[index];
          if (!track) return;
          if (!track.file_url) {
            track = (await _ensureFileUrl(track)) ?? track;
          }
          if (track.file_url && _switchToTrack(get().queue, index)) {
            set({ queueContext: context });
            return;
          }
          index = (index + 1) % queue.length;
        }
      })();
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
