import { useState } from "react";
import { Flame, RefreshCw, Music, Disc3, ListMusic } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { musicApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import { FadeIn } from "../../components/motion/FadeIn";

type RecalcResult = {
  music: number;
  album: number;
  playlist: number;
};

export const AdminHotnessPage = () => {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RecalcResult | null>(null);
  const [lastRun, setLastRun] = useState<string | null>(null);

  const handleRecalc = async () => {
    setRunning(true);
    setResult(null);
    try {
      const data = await musicApi.adminRecalculateHot();
      setResult(data);
      setLastRun(new Date().toLocaleTimeString("zh-CN"));
      toast.success(
        `热度重算完成：${data.music} 首歌曲、${data.album} 张专辑、${data.playlist} 个歌单`,
      );
    } catch (err) {
      toast.error(getApiErrorMessage(err, "热度重算失败"));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">热度管理</h1>
        <p className="panel-muted-text" style={{ marginTop: 8, marginBottom: 0 }}>
          热度基于近 7 天播放次数、收藏数、评论数加权计算，并按发布时间自然衰减。
          系统每 4 小时自动重算一次，也可在此手动触发全量重算。
        </p>
      </FadeIn>

      <FadeIn delay={0.08}>
        <section style={{ marginTop: 24 }}>
          <motion.div
            className="warm-panel"
            style={{ maxWidth: 520 }}
            whileHover={{ boxShadow: "0 4px 16px color-mix(in srgb, var(--color-brand-coral) 10%, transparent)" }}
            transition={{ duration: 0.25 }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <Flame size={20} style={{ color: "var(--color-brand-coral)" }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>全量热度重算</span>
            </div>

            <p style={{ fontSize: 13, color: "var(--color-muted)", margin: "0 0 16px", lineHeight: 1.6 }}>
              遍历所有已上架音乐、未删除专辑及全部歌单，根据当前播放数据和发布时间重新计算热度值。
              数据量大时可能需要几秒到几十秒，请耐心等待。
            </p>

            <motion.button
              type="button"
              className="btn-primary"
              onClick={() => void handleRecalc()}
              disabled={running}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
            >
              {running ? (
                <motion.span
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  style={{ display: "inline-flex" }}
                >
                  <RefreshCw size={16} />
                </motion.span>
              ) : (
                <RefreshCw size={16} />
              )}
              {running ? "计算中…" : "执行全量重算"}
            </motion.button>

            {lastRun && (
              <span style={{ marginLeft: 14, fontSize: 12, color: "var(--color-muted)" }}>
                上次执行：{lastRun}
              </span>
            )}
          </motion.div>
        </section>
      </FadeIn>

      {result && (
        <FadeIn delay={0.04}>
          <section style={{ marginTop: 20 }}>
            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", maxWidth: 520 }}>
              <motion.div
                className="dashboard-stat-card dashboard-stat-card--coral"
                style={{ flex: "1 1 140px", minWidth: 140 }}
                whileHover={{ y: -3 }}
              >
                <div className="stat-card-icon"><Music size={18} /></div>
                <div className="stat-value">{result.music}</div>
                <div className="stat-label">歌曲已更新</div>
              </motion.div>
              <motion.div
                className="dashboard-stat-card dashboard-stat-card--teal"
                style={{ flex: "1 1 140px", minWidth: 140 }}
                whileHover={{ y: -3 }}
              >
                <div className="stat-card-icon"><Disc3 size={18} /></div>
                <div className="stat-value">{result.album}</div>
                <div className="stat-label">专辑已更新</div>
              </motion.div>
              <motion.div
                className="dashboard-stat-card dashboard-stat-card--lavender"
                style={{ flex: "1 1 140px", minWidth: 140 }}
                whileHover={{ y: -3 }}
              >
                <div className="stat-card-icon"><ListMusic size={18} /></div>
                <div className="stat-value">{result.playlist}</div>
                <div className="stat-label">歌单已更新</div>
              </motion.div>
            </div>
          </section>
        </FadeIn>
      )}

      <FadeIn delay={0.16}>
        <section style={{ marginTop: 28, maxWidth: 520 }}>
          <div className="section-header">
            <h3>热度公式说明</h3>
          </div>
          <motion.div
            className="warm-panel"
            whileHover={{ boxShadow: "0 4px 16px color-mix(in srgb, var(--color-brand-ochre) 8%, transparent)" }}
            transition={{ duration: 0.25 }}
          >
            <div style={{ fontSize: 13, lineHeight: 1.8, color: "var(--color-muted)" }}>
              <p style={{ margin: "0 0 8px", fontWeight: 600, color: "var(--color-ink)" }}>
                歌曲热度
              </p>
              <code style={{ display: "block", padding: "8px 12px", background: "var(--color-surface-soft)", borderRadius: 8, marginBottom: 12, fontSize: 12 }}>
                recent = 近 7 天播放次数<br />
                engagement = ln(recent × 10 + 收藏 × 5 + 评论 × 3 + 1)<br />
                age = max(1, 距发布天数)<br />
                hot = min(1000, engagement × 100 ÷ age<sup>0.6</sup>)
              </code>
              <p style={{ margin: "0 0 8px", fontWeight: 600, color: "var(--color-ink)" }}>
                专辑 / 歌单热度
              </p>
              <p style={{ margin: 0, fontSize: 12 }}>
                = 所含全部歌曲热度的算术平均值
              </p>
            </div>
          </motion.div>
        </section>
      </FadeIn>
    </div>
  );
};
