import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Heart, Music } from "lucide-react";
import { toast } from "sonner";

import { usePlayerStore } from "../../shared/stores/playerStore";
import { usePlayerViewStore } from "../../shared/stores/playerViewStore";
import { formatAuthors, toPlayerTrack } from "../../shared/utils";
import { musicApi } from "../../shared/api/instances";
import type { MusicDetail } from "../../shared/api/types";
import { EmptyState } from "../ui/EmptyState";
import { CommentSection } from "../ui/CommentSection";
import { AddToPlaylistModal } from "../ui/AddToPlaylistModal";
import { PlayerScreenLyrics } from "./PlayerScreenLyrics";
import { PlayerScreenTransport } from "./PlayerScreenTransport";

type PlayerTab = "lyrics" | "comments";

function pickCover(music: MusicDetail): string | null {
  return music.cover_play_url ?? music.cover_home_url ?? music.cover_icon_url;
}

interface PlayerScreenProps {
  musicId: number;
  onClose: () => void;
}

const PlayerScreen = ({ musicId, onClose }: PlayerScreenProps) => {
  const playStandalone = usePlayerStore((s) => s.playStandalone);
  const togglePlay = usePlayerStore((s) => s.togglePlay);
  const currentTrack = usePlayerStore((s) => s.currentTrack);
  const isPlaying = usePlayerStore((s) => s.isPlaying);

  const [music, setMusic] = useState<MusicDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [collected, setCollected] = useState(false);
  const [playlistModalOpen, setPlaylistModalOpen] = useState(false);
  const [tab, setTab] = useState<PlayerTab>("lyrics");

  const isCurrentTrack = music != null && currentTrack?.id === music.id;
  const showPause = isCurrentTrack && isPlaying;
  const coverUrl = music ? pickCover(music) : null;
  const artistLabel = music ? formatAuthors(music.authors) || "未知艺人" : "";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setMusic(null);
      setTab("lyrics");
      try {
        const detail = await musicApi.getMusicDetail(musicId);
        if (cancelled) return;
        setMusic(detail);
        setCollected(detail.is_collected_by_me ?? false);
      } catch {
        if (!cancelled) toast.error("加载歌曲详情失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [musicId]);

  const handlePlayPause = async () => {
    if (!music) return;
    if (isCurrentTrack) {
      togglePlay();
      return;
    }
    if (!music.file_url) {
      toast.error("该歌曲暂不可播放");
      return;
    }
    await playStandalone(toPlayerTrack(music));
  };

  const handleOpenCollectModal = () => {
    if (!music) return;
    setPlaylistModalOpen(true);
  };

  return (
    <div className="ps-shell">
      {coverUrl && (
        <div className="ps-shell__bg" style={{ backgroundImage: `url(${coverUrl})` }} aria-hidden />
      )}
      <div className="ps-shell__veil" aria-hidden />
      <div className="ps-shell__glow" aria-hidden />

      <header className="ps-topbar">
        <button className="ps-topbar__close" type="button" onClick={onClose} aria-label="收起播放页">
          <ChevronDown size={22} />
          <span>收起</span>
        </button>
        <div className="ps-topbar__center">
          <span className="ps-topbar__label">正在播放</span>
        </div>
        <div className="ps-topbar__spacer" />
      </header>

      {loading ? (
        <div className="ps-state">
          <div className="ps-lyrics__spinner" />
          <p>加载中…</p>
        </div>
      ) : !music ? (
        <div className="ps-state">
          <EmptyState icon={Music} title="歌曲不存在或已被删除" accent="lavender" />
        </div>
      ) : (
        <>
          <div className="ps-body">
            <aside className="ps-media">
              <div className={`ps-media__frame${showPause ? " ps-media__frame--playing" : ""}`}>
                <div className="ps-media__art">
                  {coverUrl ? (
                    <img src={coverUrl} alt={music.title} />
                  ) : (
                    <div className="ps-media__placeholder">♪</div>
                  )}
                </div>
                <div className="ps-media__shine" aria-hidden />
              </div>

              <div className="ps-media__info">
                <h1 className="ps-media__title">{music.title}</h1>
                <p className="ps-media__artist">{artistLabel}</p>

                <div className="ps-media__chips">
                  {music.style && <span className="ps-chip">{music.style.name}</span>}
                  {music.language && <span className="ps-chip">{music.language.name}</span>}
                  {music.is_vip && <span className="ps-chip ps-chip--vip">VIP</span>}
                </div>

                <button
                  type="button"
                  className={`ps-media__fav${collected ? " ps-media__fav--on" : ""}`}
                  onClick={handleOpenCollectModal}
                >
                  <Heart size={16} fill={collected ? "currentColor" : "none"} />
                  {collected ? "已收藏" : "收藏"}
                </button>
              </div>
            </aside>

            <AddToPlaylistModal
              open={playlistModalOpen}
              musicId={music.id}
              onClose={() => setPlaylistModalOpen(false)}
              onCollectedChange={setCollected}
            />

            <section className="ps-panel">
              <nav className="ps-tabs" aria-label="播放页分区">
                <button
                  type="button"
                  className={`ps-tabs__item${tab === "lyrics" ? " ps-tabs__item--active" : ""}`}
                  onClick={() => setTab("lyrics")}
                >
                  歌词
                </button>
                <button
                  type="button"
                  className={`ps-tabs__item${tab === "comments" ? " ps-tabs__item--active" : ""}`}
                  onClick={() => setTab("comments")}
                >
                  评论
                  {music.comment_count > 0 && (
                    <span className="ps-tabs__count">{music.comment_count}</span>
                  )}
                </button>
              </nav>

              <div className="ps-panel__body">
                {tab === "lyrics" ? (
                  <PlayerScreenLyrics
                    musicId={music.id}
                    hasLyrics={Boolean(music.lyrics_url)}
                  />
                ) : (
                  <div className="ps-comments">
                    <CommentSection
                      targetType="music"
                      targetId={music.id}
                      commentCount={music.comment_count}
                    />
                  </div>
                )}
              </div>
            </section>
          </div>

          <PlayerScreenTransport
            musicId={music.id}
            isCurrentTrack={isCurrentTrack}
            showPause={showPause}
            onPlayPause={handlePlayPause}
          />
        </>
      )}
    </div>
  );
};

/** 全屏播放页：覆盖整个客户端，非路由 Tab */
export const MusicPlayerOverlay = () => {
  const isOpen = usePlayerViewStore((s) => s.isOpen);
  const musicId = usePlayerViewStore((s) => s.musicId);
  const close = usePlayerViewStore((s) => s.close);

  return (
    <AnimatePresence>
      {isOpen && musicId != null && (
        <motion.div
          className="ps-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="正在播放"
          initial={{ opacity: 0, y: 32 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 32 }}
          transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
        >
          <PlayerScreen key={musicId} musicId={musicId} onClose={close} />
        </motion.div>
      )}
    </AnimatePresence>
  );
};
