import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Shuffle,
  Repeat,
  Volume2,
  ListMusic,
  VolumeX,
  X,
  Disc,
  Clock,
} from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

import { usePlayerStore, type QueueContext } from "../../shared/stores/playerStore";
import { usePlayerViewStore } from "../../shared/stores/playerViewStore";
import { useProgressScrub } from "../../shared/useProgressScrub";
import { formatAuthors, formatTime } from "../../shared/utils";

const queueContextLabel = (ctx: QueueContext): { icon: typeof Disc; label: string } | null => {
  if (!ctx) return null;
  switch (ctx.type) {
    case "playlist":
      return { icon: ListMusic, label: ctx.name };
    case "album":
      return { icon: Disc, label: ctx.name };
    case "history":
      return { icon: Clock, label: "播放历史" };
    case "temporary":
      return { icon: ListMusic, label: "临时播放列表" };
  }
};

export const PlayerBar = () => {
  const {
    currentTrack,
    isPlaying,
    progress,
    currentTime,
    duration,
    volume,
    isShuffle,
    isRepeat,
    queue,
    queueIndex,
    queueContext,
    togglePlay,
    next,
    prev,
    seek,
    setVolume,
    toggleShuffle,
    toggleRepeat,
  } = usePlayerStore();
  const openCurrentPlayer = usePlayerViewStore((s) => s.openCurrent);

  const [showQueue, setShowQueue] = useState(false);
  const [showVolume, setShowVolume] = useState(false);

  const {
    barRef: progressBarRef,
    isDragging: isDraggingProgress,
    displayProgress,
    displayCurrentTime,
    handlePointerDown: handleProgressPointerDown,
  } = useProgressScrub({
    progress,
    currentTime,
    duration,
    seek,
    enabled: duration > 0,
  });

  return (
    <>
      <footer className="player-bar">
        {/* Song Info */}
        <div
          className={`player-song-info${currentTrack ? " player-song-info--clickable" : ""}`}
          onClick={() => currentTrack && openCurrentPlayer()}
          onKeyDown={(e) => {
            if (currentTrack && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              openCurrentPlayer();
            }
          }}
          role={currentTrack ? "button" : undefined}
          tabIndex={currentTrack ? 0 : undefined}
          title={currentTrack ? "打开播放页" : undefined}
        >
          <motion.div
            className="cover-placeholder"
            whileHover={currentTrack ? { scale: 1.05 } : undefined}
            transition={{ duration: 0.2 }}
            style={{
              background: currentTrack?.cover_icon_url
                ? undefined
                : "linear-gradient(135deg, var(--color-brand-teal) 0%, #2d5a5a 100%)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <AnimatePresence>
              {isPlaying && !currentTrack?.cover_icon_url && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0.1, 0.25, 0.1] }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 2, repeat: Infinity }}
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: "rgba(255,255,255,0.15)",
                  }}
                />
              )}
            </AnimatePresence>
            {currentTrack?.cover_icon_url ? (
              <img
                src={currentTrack.cover_icon_url}
                alt={currentTrack.title}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  position: "relative",
                  zIndex: 1,
                }}
              />
            ) : (
              <ListMusic size={20} style={{ position: "relative", zIndex: 1 }} />
            )}
          </motion.div>
          <div className="song-meta" style={{ minWidth: 0 }}>
            <AnimatePresence mode="wait">
              <motion.div
                key={currentTrack?.id ?? "idle"}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
                className="song-title"
              >
                {currentTrack?.title ?? "选择一首歌曲开始播放"}
              </motion.div>
            </AnimatePresence>
            <div className="song-artist">
              {currentTrack ? formatAuthors(currentTrack.authors, "EchoMemory") : "EchoMemory"}
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="player-controls">
          <div className="player-buttons">
            <motion.button
              className={`player-btn ${isShuffle ? "active" : ""}`}
              onClick={toggleShuffle}
              whileHover={{ scale: 1.12 }}
              whileTap={{ scale: 0.92 }}
              type="button"
              title="随机播放"
            >
              <Shuffle size={16} />
            </motion.button>
            <motion.button
              className="player-btn"
              onClick={prev}
              whileHover={{ scale: 1.12 }}
              whileTap={{ scale: 0.92 }}
              type="button"
              title="上一首"
            >
              <SkipBack size={18} />
            </motion.button>
            <motion.button
              className="player-btn play"
              onClick={togglePlay}
              whileHover={{ scale: 1.08 }}
              whileTap={{ scale: 0.93 }}
              type="button"
              title={isPlaying ? "暂停" : "播放"}
            >
              <AnimatePresence mode="wait">
                {isPlaying ? (
                  <motion.div
                    key="pause"
                    initial={{ scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.5, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Pause size={18} />
                  </motion.div>
                ) : (
                  <motion.div
                    key="play"
                    initial={{ scale: 0.5, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.5, opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Play size={18} fill="white" />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.button>
            <motion.button
              className="player-btn"
              onClick={next}
              whileHover={{ scale: 1.12 }}
              whileTap={{ scale: 0.92 }}
              type="button"
              title="下一首"
            >
              <SkipForward size={18} />
            </motion.button>
            <motion.button
              className={`player-btn ${isRepeat ? "active" : ""}`}
              onClick={toggleRepeat}
              whileHover={{ scale: 1.12 }}
              whileTap={{ scale: 0.92 }}
              type="button"
              title="循环"
            >
              <Repeat size={16} />
            </motion.button>
          </div>

          <div className="player-progress">
            <span className="time">{formatTime(displayCurrentTime)}</span>
            <div
              className="player-progress-bar"
              ref={progressBarRef}
              onPointerDown={handleProgressPointerDown}
              style={{ cursor: "pointer", touchAction: "none" }}
            >
              <motion.div
                className="fill"
                animate={{ width: `${displayProgress}%` }}
                transition={{ duration: isDraggingProgress ? 0 : 0.3, ease: [0.25, 0.1, 0.25, 1] }}
              />
              <motion.div
                style={{
                  position: "absolute",
                  left: `${displayProgress}%`,
                  top: "50%",
                  transform: "translate(-50%, -50%)",
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "var(--color-accent)",
                  boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
                  cursor: "pointer",
                }}
                whileHover={{ scale: 1.4 }}
                transition={{ duration: 0.15 }}
              />
            </div>
            <span className="time">{formatTime(duration)}</span>
          </div>
        </div>

        {/* Extra */}
        <div className="player-extra">
          <div
            style={{ position: "relative" }}
            onMouseEnter={() => setShowVolume(true)}
            onMouseLeave={() => setShowVolume(false)}
          >
            <motion.button
              className="player-btn"
              onClick={() => setVolume(volume > 0 ? 0 : 0.8)}
              whileHover={{ scale: 1.12 }}
              whileTap={{ scale: 0.92 }}
              type="button"
              title="音量"
            >
              {volume < 0.01 ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </motion.button>
            <AnimatePresence>
              {showVolume && (
                <motion.div
                  initial={{ opacity: 0, y: 4, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  style={{
                    position: "absolute",
                    bottom: "calc(100% + 8px)",
                    left: "50%",
                    transform: "translateX(-50%)",
                    width: 32,
                    height: 100,
                    background: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    padding: "8px 0",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 100,
                  }}
                >
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.01}
                    value={volume}
                    onChange={(e) => setVolume(parseFloat(e.target.value))}
                    style={{
                      WebkitAppearance: "slider-vertical",
                      width: 4,
                      height: 80,
                    }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <motion.button
            className={`player-btn ${showQueue ? "active" : ""}`}
            onClick={() => setShowQueue(!showQueue)}
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.92 }}
            type="button"
            title="播放队列"
          >
            <ListMusic size={16} />
          </motion.button>
        </div>
      </footer>

      {/* Queue Panel */}
      <AnimatePresence>
        {showQueue && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "fixed",
              bottom: 72,
              right: 16,
              width: 320,
              maxHeight: 400,
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 12,
              zIndex: 50,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 16px",
                borderBottom: "1px solid var(--color-border)",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontWeight: 600, fontSize: 14 }}>播放队列</span>
                {(() => {
                  const ctx = queueContextLabel(queueContext);
                  if (ctx) {
                    return (
                      <span style={{ fontSize: 11, color: "var(--color-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                        <ctx.icon size={11} />
                        {ctx.label}
                      </span>
                    );
                  }
                  return null;
                })()}
              </div>
              <button
                onClick={() => setShowQueue(false)}
                style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}
              >
                <X size={16} />
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1, padding: "8px 0" }}>
              {queue.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: "var(--color-muted)", fontSize: 13 }}>
                  队列中暂无歌曲
                </div>
              ) : (
                queue.map((track, i) => (
                  <div
                    key={`${track.id}-${i}`}
                    onClick={() => usePlayerStore.getState().playQueue(queue, i, queueContext)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 16px",
                      cursor: "pointer",
                      background: i === queueIndex ? "rgba(0,0,0,0.04)" : "transparent",
                    }}
                  >
                    <span style={{ fontSize: 12, color: "var(--color-muted)", width: 20, textAlign: "center" }}>
                      {i === queueIndex && isPlaying ? "▶" : i + 1}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 500,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {track.title}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--color-muted)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {formatAuthors(track.authors)}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};
