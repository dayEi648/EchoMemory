import { motion } from "framer-motion";
import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX } from "lucide-react";

import { usePlayerStore } from "../../shared/stores/playerStore";
import { useProgressScrub } from "../../shared/useProgressScrub";
import { formatTime } from "../../shared/utils";

interface PlayerScreenTransportProps {
  /** 当前播放页展示的歌曲 id，用于判断是否控制当前曲目 */
  musicId: number;
  onPlayPause: () => void;
  isCurrentTrack: boolean;
  showPause: boolean;
}

/** 播放页底部传输控制条（进度、播放、音量） */
export const PlayerScreenTransport = ({
  musicId,
  onPlayPause,
  isCurrentTrack,
  showPause,
}: PlayerScreenTransportProps) => {
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const progress = usePlayerStore((s) => s.progress);
  const currentTime = usePlayerStore((s) => s.currentTime);
  const duration = usePlayerStore((s) => s.duration);
  const volume = usePlayerStore((s) => s.volume);
  const seek = usePlayerStore((s) => s.seek);
  const setVolume = usePlayerStore((s) => s.setVolume);
  const next = usePlayerStore((s) => s.next);
  const prev = usePlayerStore((s) => s.prev);

  const canControl = isCurrentTrack && currentTrack?.id === musicId;

  const {
    barRef,
    isDragging,
    displayProgress: scrubProgress,
    displayCurrentTime: scrubCurrentTime,
    handlePointerDown,
  } = useProgressScrub({
    progress: canControl ? progress : 0,
    currentTime: canControl ? currentTime : 0,
    duration: canControl ? duration : 0,
    seek,
    enabled: canControl,
  });

  const displayProgress = canControl ? scrubProgress : 0;
  const displayCurrent = canControl ? scrubCurrentTime : 0;
  const displayDuration = canControl ? duration : 0;

  return (
    <footer className="ps-dock">
      <div className="ps-dock__progress-row">
        <span className="ps-dock__time">{formatTime(displayCurrent)}</span>
        <div
          ref={barRef}
          className={`ps-dock__bar${canControl ? "" : " ps-dock__bar--disabled"}`}
          onPointerDown={handlePointerDown}
          role="slider"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={displayProgress}
          aria-label="播放进度"
        >
          <div className="ps-dock__bar-track" />
          <motion.div
            className="ps-dock__bar-fill"
            animate={{ width: `${displayProgress}%` }}
            transition={{ duration: isDragging ? 0 : 0.25 }}
          />
          <motion.div
            className="ps-dock__bar-thumb"
            animate={{ left: `${displayProgress}%` }}
            transition={{ duration: isDragging ? 0 : 0.25 }}
          />
        </div>
        <span className="ps-dock__time">{formatTime(displayDuration)}</span>
      </div>

      <div className="ps-dock__controls">
        <button
          className="ps-dock__btn"
          type="button"
          onClick={prev}
          disabled={!canControl}
          aria-label="上一首"
        >
          <SkipBack size={20} />
        </button>

        <motion.button
          className="ps-dock__play"
          type="button"
          onClick={onPlayPause}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.94 }}
          aria-label={showPause ? "暂停" : "播放"}
        >
          {showPause ? <Pause size={26} fill="currentColor" /> : <Play size={26} fill="currentColor" />}
        </motion.button>

        <button
          className="ps-dock__btn"
          type="button"
          onClick={next}
          disabled={!canControl}
          aria-label="下一首"
        >
          <SkipForward size={20} />
        </button>

        <div className="ps-dock__volume">
          <button
            className="ps-dock__btn"
            type="button"
            onClick={() => setVolume(volume > 0 ? 0 : 0.8)}
            aria-label="音量"
          >
            {volume < 0.01 ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <input
            type="range"
            className="ps-dock__volume-slider"
            min={0}
            max={1}
            step={0.01}
            value={volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            aria-label="音量调节"
          />
        </div>
      </div>
    </footer>
  );
};
