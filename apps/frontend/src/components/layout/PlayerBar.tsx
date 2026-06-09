import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Shuffle,
  Repeat,
  Volume2,
  ListMusic,
} from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export const PlayerBar = () => {
  const [playing, setPlaying] = useState(false);
  const [progress] = useState(30);

  return (
    <footer className="player-bar">
      {/* Song Info */}
      <div className="player-song-info">
        <motion.div
          className="cover-placeholder"
          whileHover={{ scale: 1.05 }}
          transition={{ duration: 0.2 }}
          style={{
            background: "linear-gradient(135deg, #1a3a3a 0%, #2d5a5a 100%)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* subtle animated pulse when playing */}
          <AnimatePresence>
            {playing && (
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
          <ListMusic size={20} style={{ position: "relative", zIndex: 1 }} />
        </motion.div>
        <div className="song-meta" style={{ minWidth: 0 }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={playing ? "playing" : "idle"}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="song-title"
            >
              {playing ? "正在播放" : "选择一首歌曲开始播放"}
            </motion.div>
          </AnimatePresence>
          <div className="song-artist">EchoMemory</div>
        </div>
      </div>

      {/* Controls */}
      <div className="player-controls">
        <div className="player-buttons">
          <motion.button
            className="player-btn"
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.92 }}
            type="button"
            title="随机播放"
          >
            <Shuffle size={16} />
          </motion.button>
          <motion.button
            className="player-btn"
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.92 }}
            type="button"
            title="上一首"
          >
            <SkipBack size={18} />
          </motion.button>
          <motion.button
            className="player-btn play"
            onClick={() => setPlaying(!playing)}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.93 }}
            type="button"
            title={playing ? "暂停" : "播放"}
          >
            <AnimatePresence mode="wait">
              {playing ? (
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
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.92 }}
            type="button"
            title="下一首"
          >
            <SkipForward size={18} />
          </motion.button>
          <motion.button
            className="player-btn"
            whileHover={{ scale: 1.12 }}
            whileTap={{ scale: 0.92 }}
            type="button"
            title="循环"
          >
            <Repeat size={16} />
          </motion.button>
        </div>

        <div className="player-progress">
          <span className="time">1:12</span>
          <div className="player-progress-bar">
            <motion.div
              className="fill"
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
            />
            {/* progress handle */}
            <motion.div
              style={{
                position: "absolute",
                left: `${progress}%`,
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
          <span className="time">3:48</span>
        </div>
      </div>

      {/* Extra */}
      <div className="player-extra">
        <motion.button
          className="player-btn"
          whileHover={{ scale: 1.12 }}
          whileTap={{ scale: 0.92 }}
          type="button"
          title="音量"
        >
          <Volume2 size={16} />
        </motion.button>
        <motion.button
          className="player-btn"
          whileHover={{ scale: 1.12 }}
          whileTap={{ scale: 0.92 }}
          type="button"
          title="播放队列"
        >
          <ListMusic size={16} />
        </motion.button>
      </div>
    </footer>
  );
};
