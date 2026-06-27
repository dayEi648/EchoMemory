import { useEffect, useRef, useState } from "react";
import {
  Compass,
  Heart,
  Play,
  SkipBack,
  SkipForward,
  ThumbsDown,
  Loader2,
  Sparkles,
  Send,
  Music,
  Disc3,
  Library,
} from "lucide-react";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";

import { roamApi } from "../shared/api/instances";
import type { RoamState, RoamReport } from "../shared/api/types";
import { formatAuthors } from "../shared/utils";
import { usePlayMusic } from "../shared/usePlayMusic";
import { FadeIn } from "../components/motion/FadeIn";
import { getApiErrorMessage } from "../shared/apiError";

type Phase = "idle" | "roaming" | "exhausted" | "report";
type InitState = "loading" | "ready";

/** 判断 API 错误是否因曲库无可选歌曲（404） */
const isExhaustedError = (err: unknown): boolean =>
  typeof err === "object" && err !== null && "status" in err && (err as { status: number }).status === 404;

export const RoamPage = () => {
  const { playMusicListItem } = usePlayMusic();
  const [phase, setPhase] = useState<Phase>("idle");
  const [state, setState] = useState<RoamState | null>(null);
  const [report, setReport] = useState<RoamReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [favoriting, setFavoriting] = useState(false);
  const [guideText, setGuideText] = useState("");
  const [guiding, setGuiding] = useState(false);
  const [init, setInit] = useState<InitState>("loading");
  const [emptyLibrary, setEmptyLibrary] = useState(false);
  const [exhaustedStats, setExhaustedStats] = useState<{ played: number; liked: number } | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  // 挂载时检查是否有活跃的漫游 session，有则恢复
  useEffect(() => {
    let cancelled = false;
    const checkSession = async () => {
      try {
        const s = await roamApi.getState();
        if (cancelled) return;
        setState(s);
        setPhase("roaming");
      } catch {
        // 无活跃 session → 展示 idle 状态
      } finally {
        if (!cancelled) setInit("ready");
      }
    };
    checkSession();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- actions ---
  const startRoam = async () => {
    setLoading(true);
    try {
      const s = await roamApi.start();
      if (cancelledRef.current) return;
      setState(s);
      setPhase("roaming");
      void playMusicListItem(s.current_song);
    } catch (err) {
      if (!cancelledRef.current) {
        if (isExhaustedError(err)) {
          setEmptyLibrary(true);
        } else {
          toast.error(getApiErrorMessage(err, "开始漫游失败"));
        }
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  };

  const doNext = async () => {
    if (!state || loading) return;
    setLoading(true);
    try {
      const s = await roamApi.next();
      if (cancelledRef.current) return;
      setState(s);
      void playMusicListItem(s.current_song);
    } catch (err) {
      if (!cancelledRef.current) {
        if (isExhaustedError(err)) {
          // 没有更多歌曲可探索 → 优雅结束
          setExhaustedStats({
            played: state.playlist.length,
            liked: 0, // 无法从当前 state 精确统计，设为 0
          });
          setPhase("exhausted");
        } else {
          toast.error(getApiErrorMessage(err, "切换失败"));
        }
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  };

  const doPrev = async () => {
    if (!state || loading) return;
    setLoading(true);
    try {
      const s = await roamApi.prev();
      if (cancelledRef.current) return;
      setState(s);
      void playMusicListItem(s.current_song);
    } catch (err) {
      if (!cancelledRef.current)
        toast.error(getApiErrorMessage(err, "切换失败"));
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  };

  const doFavorite = async () => {
    if (!state || favoriting) return;
    const song = state.current_song;
    setFavoriting(true);
    try {
      await roamApi.favorite(song.id);
      toast.success(`已收藏「${song.title}」`);
      // 更新本地收藏状态
      setState((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          current_song: { ...prev.current_song, is_collected_by_me: true },
        };
      });
      // 刷新状态以获取更新后的池
      const fresh = await roamApi.getState();
      if (!cancelledRef.current) setState(fresh);
    } catch (err) {
      if (!cancelledRef.current)
        toast.error(getApiErrorMessage(err, "收藏失败"));
    } finally {
      if (!cancelledRef.current) setFavoriting(false);
    }
  };

  const doDislike = async (withReasons?: Record<string, unknown>) => {
    if (!state || loading) return;
    const song = state.current_song;
    try {
      await roamApi.dislike(song.id, withReasons);
      toast.success("已跳过，下一首将避开相似歌曲");
      // 自动切到下一首
      await doNext();
    } catch (err) {
      if (!cancelledRef.current)
        toast.error(getApiErrorMessage(err, "操作失败"));
    }
  };

  const doGuide = async () => {
    const hint = guideText.trim();
    if (!hint || guiding) return;
    setGuiding(true);
    try {
      const res = await roamApi.guide(hint);
      if (cancelledRef.current) return;
      setState(res.new_state);
      setGuideText("");
      toast.success(`🎯 ${res.parsed_intent}`);
      void playMusicListItem(res.new_state.current_song);
    } catch (err) {
      if (!cancelledRef.current)
        toast.error(getApiErrorMessage(err, "引导失败"));
    } finally {
      if (!cancelledRef.current) setGuiding(false);
    }
  };

  const doEnd = async () => {
    if (!state || loading) return;
    setLoading(true);
    try {
      const r = await roamApi.end();
      if (cancelledRef.current) return;
      setReport(r);
      setPhase("report");
    } catch (err) {
      if (!cancelledRef.current)
        toast.error(getApiErrorMessage(err, "结束失败"));
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  };

  const doRestart = () => {
    setReport(null);
    setState(null);
    setPhase("idle");
  };

  // --- render helpers ---
  const song = state?.current_song ?? null;
  const coverUrl = song?.cover_icon_url ?? null;
  const reason = state?.recommend_reason ?? null;
  const progress = state
    ? `${state.position + 1} / ${state.playlist.length}`
    : "";

  return (
    <div className="page-content roam-page">
      {/* ---------- Init Loading ---------- */}
      {init === "loading" && (
        <div className="roam-idle">
          <Loader2 size={32} className="animate-spin" style={{ color: "#b8a4ed" }} />
        </div>
      )}

      {/* ---------- Empty Library ---------- */}
      {init === "ready" && emptyLibrary && (
        <FadeIn>
          <div className="roam-idle">
            <div className="roam-idle-icon roam-idle-icon--muted">
              <Library size={48} />
            </div>
            <h1 className="roam-idle-title">曲库空空</h1>
            <p className="roam-idle-desc">
              还没有可探索的音乐。
              <br />
              先去导入几首歌，再来开启漫游吧。
            </p>
          </div>
        </FadeIn>
      )}

      {/* ---------- Idle ---------- */}
      {init === "ready" && !emptyLibrary && phase === "idle" && (
        <FadeIn>
          <div className="roam-idle">
            <div className="roam-idle-icon">
              <Compass size={48} />
            </div>
            <h1 className="roam-idle-title">私人漫游</h1>
            <p className="roam-idle-desc">
              随机出发，随心探索。收藏感兴趣的歌曲，跳过不感兴趣的，
              <br />
              AI 会逐渐理解你的品味，带你发现更多惊喜。
            </p>
            <button
              type="button"
              className="roam-start-btn"
              onClick={startRoam}
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  准备中...
                </>
              ) : (
                <>
                  <Sparkles size={20} />
                  开始漫游
                </>
              )}
            </button>
          </div>
        </FadeIn>
      )}

      {/* ---------- Exhausted ---------- */}
      {phase === "exhausted" && (
        <FadeIn>
          <div className="roam-idle">
            <div className="roam-idle-icon roam-idle-icon--muted">
              <Sparkles size={48} />
            </div>
            <h1 className="roam-idle-title">探索完毕</h1>
            <p className="roam-idle-desc">
              {exhaustedStats
                ? `你已听完当前曲库中所有可探索的 ${exhaustedStats.played} 首歌。`
                : "当前曲库中已经没有更多可探索的歌曲了。"}
              <br />
              等待曲库扩充后再来发现新惊喜。
            </p>
            <button
              type="button"
              className="roam-start-btn roam-start-btn--restart"
              onClick={() => {
                setPhase("idle");
                setState(null);
                setExhaustedStats(null);
              }}
            >
              <Compass size={18} />
              重新开始
            </button>
          </div>
        </FadeIn>
      )}

      {/* ---------- Roaming ---------- */}
      {phase === "roaming" && song && (
        <div className="roam-active">
          {/* Header */}
          <FadeIn>
            <div className="roam-header">
              <div className="roam-header-left">
                <Compass size={22} className="roam-header-icon" />
                <div>
                  <h1 className="roam-title">私人漫游</h1>
                  <span className="roam-progress">{progress}</span>
                </div>
              </div>
              <button
                type="button"
                className="roam-end-btn"
                onClick={doEnd}
                disabled={loading}
              >
                结束漫游
              </button>
            </div>
          </FadeIn>

          {/* Main Card */}
          <FadeIn delay={0.05}>
            <motion.div
              className="roam-cover-card"
              key={song.id}
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
            >
              {/* Cover */}
              <div className="roam-cover-art">
                {coverUrl ? (
                  <img src={coverUrl} alt={song.title} />
                ) : (
                  <div className="roam-cover-fallback">
                    <Disc3 size={64} />
                  </div>
                )}
              </div>

              {/* Song Info */}
              <div className="roam-song-info">
                <h2 className="roam-song-title">{song.title}</h2>
                <p className="roam-song-artist">{formatAuthors(song.authors)}</p>
                {song.is_vip && <span className="roam-vip-badge">VIP</span>}
              </div>

              {/* AI Reason */}
              <AnimatePresence mode="wait">
                {reason ? (
                  <motion.div
                    className="roam-reason"
                    key={reason}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    <Sparkles size={14} className="roam-reason-icon" />
                    <span>{reason}</span>
                  </motion.div>
                ) : loading ? (
                  <div className="roam-reason roam-reason--loading">
                    <Loader2 size={14} className="animate-spin" />
                    <span>寻找理由中...</span>
                  </div>
                ) : null}
              </AnimatePresence>
            </motion.div>
          </FadeIn>

          {/* Controls */}
          <FadeIn delay={0.1}>
            <div className="roam-controls">
              <button
                type="button"
                className="roam-btn roam-btn--dislike"
                onClick={() => doDislike()}
                disabled={loading}
                title="不收藏，跳过"
              >
                <ThumbsDown size={20} />
              </button>

              <button
                type="button"
                className="roam-btn roam-btn--prev"
                onClick={doPrev}
                disabled={loading || (state?.position ?? -1) === 0}
              >
                <SkipBack size={22} />
              </button>

              <button
                type="button"
                className="roam-btn roam-btn--play"
                onClick={() => song && playMusicListItem(song)}
                disabled={loading}
              >
                <Play size={24} fill="currentColor" />
              </button>

              <button
                type="button"
                className="roam-btn roam-btn--next"
                onClick={doNext}
                disabled={loading}
              >
                <SkipForward size={22} />
              </button>

              <button
                type="button"
                className={`roam-btn roam-btn--fav${
                  song.is_collected_by_me ? " roam-btn--fav-active" : ""
                }`}
                onClick={doFavorite}
                disabled={favoriting || song.is_collected_by_me}
                title={song.is_collected_by_me ? "已收藏" : "收藏"}
              >
                <Heart
                  size={20}
                  fill={song.is_collected_by_me ? "currentColor" : "none"}
                />
              </button>
            </div>
          </FadeIn>

          {/* Guide Input */}
          <FadeIn delay={0.15}>
            <div className="roam-guide">
              <div className="roam-guide-input-wrap">
                <input
                  type="text"
                  className="roam-guide-input"
                  placeholder="告诉 AI 你想听什么方向..."
                  value={guideText}
                  onChange={(e) => setGuideText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doGuide()}
                  disabled={guiding}
                  maxLength={100}
                />
                <button
                  type="button"
                  className="roam-guide-send"
                  onClick={doGuide}
                  disabled={!guideText.trim() || guiding}
                >
                  {guiding ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Send size={16} />
                  )}
                </button>
              </div>
            </div>
          </FadeIn>
        </div>
      )}

      {/* ---------- Report ---------- */}
      {phase === "report" && report && (
        <FadeIn>
          <div className="roam-report">
            <div className="roam-report-card">
              <div className="roam-report-header">
                <Sparkles size={28} />
                <h2>漫游报告</h2>
              </div>

              <div className="roam-report-stats">
                <div className="roam-stat">
                  <span className="roam-stat-num">{report.total_songs}</span>
                  <span className="roam-stat-label">探索歌曲</span>
                </div>
                <div className="roam-stat">
                  <span className="roam-stat-num roam-stat-num--fav">
                    {report.favorited_count}
                  </span>
                  <span className="roam-stat-label">收藏</span>
                </div>
                <div className="roam-stat">
                  <span className="roam-stat-num roam-stat-num--dislike">
                    {report.disliked_count}
                  </span>
                  <span className="roam-stat-label">跳过</span>
                </div>
              </div>

              {/* AI Summary */}
              <div className="roam-report-summary">
                <p>{report.taste_summary}</p>
                {report.recommendation && (
                  <p className="roam-report-recommendation">
                    💡 {report.recommendation}
                  </p>
                )}
              </div>

              {/* Favorited Songs */}
              {report.favorited_songs.length > 0 && (
                <div className="roam-report-favs">
                  <h3>你收藏的歌曲</h3>
                  <ul className="roam-report-favlist">
                    {report.favorited_songs.map((s) => (
                      <li
                        key={s.id}
                        className="roam-report-favitem"
                        onClick={() => playMusicListItem(s)}
                      >
                        <Music size={14} />
                        <span className="roam-report-favname">
                          {s.title} — {formatAuthors(s.authors)}
                        </span>
                        <Play size={12} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <button
                type="button"
                className="roam-start-btn roam-start-btn--restart"
                onClick={doRestart}
              >
                <Compass size={18} />
                再次漫游
              </button>
            </div>
          </div>
        </FadeIn>
      )}

      {/* Loading Overlay */}
      <AnimatePresence>
        {loading && phase === "roaming" && (
          <motion.div
            className="roam-loading-bar"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Loader2 size={18} className="animate-spin" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
