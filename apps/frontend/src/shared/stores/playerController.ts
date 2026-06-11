/** 播放器 Audio 控制器：封装元素生命周期与事件绑定，便于测试注入 fake audio。 */

export type PlayerControllerHandlers = {
  onTimeUpdate: (currentTime: number, duration: number) => void;
  onEnded: () => void;
  onError: () => void;
  onPlay: () => void;
  onPause: () => void;
  onLoadedMetadata: (duration: number) => void;
};

export type PlayerController = {
  audio: HTMLAudioElement;
  bind: (handlers: PlayerControllerHandlers) => void;
  destroy: () => void;
};

export function createPlayerController(
  audio: HTMLAudioElement = new Audio(),
  initialVolume = 0.8,
): PlayerController {
  audio.volume = initialVolume;
  const listeners = new Map<string, EventListener>();

  const bind = (handlers: PlayerControllerHandlers) => {
    destroy();

    const onTimeUpdate = () => {
      handlers.onTimeUpdate(audio.currentTime, audio.duration || 0);
    };
    const onEnded = () => handlers.onEnded();
    const onError = () => handlers.onError();
    const onPlay = () => handlers.onPlay();
    const onPause = () => handlers.onPause();
    const onLoadedMetadata = () => handlers.onLoadedMetadata(audio.duration || 0);

    listeners.set("timeupdate", onTimeUpdate);
    listeners.set("ended", onEnded);
    listeners.set("error", onError);
    listeners.set("play", onPlay);
    listeners.set("pause", onPause);
    listeners.set("loadedmetadata", onLoadedMetadata);

    for (const [event, listener] of listeners) {
      audio.addEventListener(event, listener);
    }
  };

  const destroy = () => {
    for (const [event, listener] of listeners) {
      audio.removeEventListener(event, listener);
    }
    listeners.clear();
  };

  return { audio, bind, destroy };
}

/** 模块级默认控制器，供 playerStore 使用。 */
export const defaultPlayerController = createPlayerController();
