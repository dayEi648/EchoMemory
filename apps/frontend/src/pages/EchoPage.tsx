import { useEffect, useMemo, useState } from "react";
import {
  Sparkles,
  Brain,
  Heart,
  Music,
  Palette,
  Globe,
  Clock,
  RefreshCw,
  Volume2,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { EmptyState } from "../components/ui/EmptyState";
import { PageTitle } from "../components/ui/PageTitle";
import { FadeIn } from "../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../components/motion/StaggerContainer";
import { userApi } from "../shared/api/instances";
import type { UserEcho, UserTag } from "../shared/api/types";
import { getApiErrorMessage } from "../shared/apiError";

type TagSection = {
  key: keyof Pick<UserEcho, "emotion_tags" | "interest_tags" | "styles" | "languages">;
  icon: typeof Brain;
  title: string;
  cardClass: string;
  emptyText: string;
};

const TAG_SECTIONS: TagSection[] = [
  {
    key: "emotion_tags",
    icon: Heart,
    title: "情绪偏好",
    cardClass: "feature-card feature-card-pink",
    emptyText: "继续听歌，AI 会捕捉你偏爱的情绪色彩",
  },
  {
    key: "interest_tags",
    icon: Brain,
    title: "兴趣标签",
    cardClass: "feature-card feature-card-lavender",
    emptyText: "探索更多音乐，让兴趣画像丰富起来",
  },
  {
    key: "styles",
    icon: Palette,
    title: "风格偏好",
    cardClass: "feature-card feature-card-teal",
    emptyText: "风格偏好会随播放历史自动积累",
  },
  {
    key: "languages",
    icon: Globe,
    title: "语言偏好",
    cardClass: "feature-card feature-card-ochre",
    emptyText: "多听不同语言的歌单，拓展语言偏好",
  },
];

const MAX_HOUR_BAR_HEIGHT = 96;

/** 将 24 小时分布归一化到最大高度，用于柱状图展示 */
function normalizeHourlyDistribution(distribution: number[]): number[] {
  const max = Math.max(1, ...distribution);
  return distribution.map((count) => (count / max) * MAX_HOUR_BAR_HEIGHT);
}

/** 格式化小时标签 */
function formatHourLabel(hour: number): string {
  return `${String(hour).padStart(2, "0")}:00`;
}

/** 判断当前时段是否属于高峰期 */
function getPeakHours(distribution: number[]): Set<number> {
  const max = Math.max(0, ...distribution);
  if (max === 0) return new Set();
  const threshold = max * 0.6;
  return new Set(distribution.map((v, i) => (v >= threshold ? i : -1)).filter((i) => i >= 0));
}

/** 生成偏好时段的中文描述 */
function describeActiveHours(distribution: number[]): string {
  const peak = getPeakHours(distribution);
  if (peak.size === 0) return "继续听歌，活跃时段会逐渐清晰";

  const ranges: string[] = [];
  const sorted = Array.from(peak).sort((a, b) => a - b);
  let start = sorted[0];
  let prev = sorted[0];

  for (let i = 1; i <= sorted.length; i++) {
    const current = sorted[i];
    if (current === undefined || current !== prev + 1) {
      if (start === prev) {
        ranges.push(formatHourLabel(start));
      } else {
        ranges.push(`${formatHourLabel(start)} - ${formatHourLabel(prev + 1)}`);
      }
      start = current ?? start;
    }
    prev = current ?? prev;
  }

  return `你常在 ${ranges.join("、")} 听音乐`;
}

function TagList({ tags, emptyText }: { tags: UserTag[]; emptyText: string }) {
  if (tags.length === 0) {
    return <p className="echo-card-desc">{emptyText}</p>;
  }
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
      {tags.map((tag) => (
        <span
          key={tag.tag_id}
          style={{
            display: "inline-flex",
            alignItems: "center",
            padding: "6px 12px",
            borderRadius: 9999,
            background: "rgba(255,255,255,0.25)",
            fontSize: 13,
            fontWeight: 500,
            color: "inherit",
          }}
        >
          {tag.name}
        </span>
      ))}
    </div>
  );
}

export const EchoPage = () => {
  const [echo, setEcho] = useState<UserEcho | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);

  const loadEcho = async () => {
    setLoading(true);
    try {
      const data = await userApi.getMyEcho();
      setEcho(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "加载个人回声失败"));
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await userApi.recalculateMyTags?.();
      toast.success("偏好画像已重新计算");
      await loadEcho();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "重新计算失败"));
    } finally {
      setRecalculating(false);
    }
  };

  useEffect(() => {
    void loadEcho();
  }, []);

  const hourlyBars = useMemo(
    () => normalizeHourlyDistribution(echo?.hourly_distribution ?? []),
    [echo?.hourly_distribution],
  );

  const activeHoursDescription = useMemo(
    () => describeActiveHours(echo?.hourly_distribution ?? []),
    [echo?.hourly_distribution],
  );

  const hasAnyTags = useMemo(
    () =>
      TAG_SECTIONS.some((section) => (echo?.[section.key]?.length ?? 0) > 0),
    [echo],
  );

  return (
    <div>
      <FadeIn>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <PageTitle icon={Sparkles} iconSize={18} iconAccent="lavender">
            个人回声
          </PageTitle>
          <motion.button
            type="button"
            className="ghost-button"
            onClick={handleRecalculate}
            disabled={recalculating || loading}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              opacity: recalculating || loading ? 0.6 : 1,
            }}
          >
            <RefreshCw size={14} className={recalculating ? "spin-icon" : ""} />
            {recalculating ? "计算中..." : "重新计算偏好"}
          </motion.button>
        </div>
      </FadeIn>

      <FadeIn delay={0.08}>
        <p className="page-lead">
          EchoMemory 根据你的播放历史、收藏与 AI 对话，持续描绘你的音乐肖像。
        </p>
      </FadeIn>

      {loading ? (
        <FadeIn delay={0.12}>
          <div className="empty-state">
            <p>正在生成你的个人回声...</p>
          </div>
        </FadeIn>
      ) : (
        <>
          {/* AI 画像摘要 */}
          <FadeIn delay={0.12}>
            <motion.div
              className="feature-card feature-card-cream"
              style={{ marginBottom: 24 }}
              whileHover={{ y: -2 }}
              transition={{ duration: 0.25 }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                <div
                  className="icon-accent-bg icon-accent-bg--lavender"
                  style={{ flexShrink: 0 }}
                >
                  <Brain size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 className="echo-card-title">AI 画像摘要</h4>
                  <p className="echo-card-desc" style={{ marginTop: 8 }}>
                    {echo?.profile?.trim()
                      ? echo.profile
                      : "你还没有足够的 AI 对话记录，多和 AI 助手聊聊音乐，这里会生成专属画像摘要。"}
                  </p>
                </div>
              </div>
            </motion.div>
          </FadeIn>

          {/* 标签偏好卡片 */}
          {hasAnyTags ? (
            <StaggerContainer staggerDelay={0.08} className="echo-cards-grid">
              {TAG_SECTIONS.map((section) => {
                const tags = echo?.[section.key] ?? [];
                return (
                  <StaggerItem key={section.key} className="echo-card-item">
                    <motion.div
                      className={section.cardClass}
                      whileHover={{ y: -4 }}
                      transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
                    >
                      <motion.div
                        className="echo-card-icon"
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: 12,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          marginBottom: 14,
                          background: "rgba(255,255,255,0.2)",
                        }}
                        whileHover={{ rotate: [0, -5, 5, 0] }}
                        transition={{ duration: 0.4 }}
                      >
                        <section.icon size={20} />
                      </motion.div>
                      <h4 className="echo-card-title">{section.title}</h4>
                      <TagList tags={tags} emptyText={section.emptyText} />
                    </motion.div>
                  </StaggerItem>
                );
              })}
            </StaggerContainer>
          ) : (
            <FadeIn delay={0.16}>
              <EmptyState
                icon={Music}
                title="偏好画像还在生长"
                description="多去发现和收藏音乐，AI 会在这里汇总你的情绪、兴趣、风格与语言偏好。"
                accent="lavender"
              />
            </FadeIn>
          )}

          {/* 活跃时段分布 */}
          <FadeIn delay={0.35}>
            <section style={{ marginTop: 32 }}>
              <div className="section-header">
                <h3>
                  <Clock size={18} style={{ verticalAlign: "-3px", marginRight: 8 }} />
                  听歌活跃时段
                </h3>
              </div>
              <motion.div
                className="warm-panel"
                whileHover={{ boxShadow: "0 4px 16px color-mix(in srgb, var(--color-brand-ochre) 12%, transparent)" }}
                transition={{ duration: 0.25 }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 16,
                    color: "var(--color-muted)",
                    fontSize: 14,
                  }}
                >
                  <Volume2 size={16} />
                  <span>
                    累计播放 {(echo?.total_play_count ?? 0).toLocaleString()} 次
                    {(echo?.total_play_count ?? 0) > 0 && ` · ${activeHoursDescription}`}
                  </span>
                </div>

                {echo && echo.total_play_count > 0 ? (
                  <div style={{ overflowX: "auto" }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-end",
                        gap: 4,
                        minWidth: 720,
                        height: 140,
                        paddingBottom: 24,
                        borderBottom: "1px solid var(--color-hairline)",
                      }}
                    >
                      {hourlyBars.map((height, hour) => (
                        <div
                          key={hour}
                          style={{
                            flex: 1,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "flex-end",
                            gap: 4,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 10,
                              color: "var(--color-muted-soft)",
                              opacity: height > 0 ? 1 : 0,
                            }}
                          >
                            {echo.hourly_distribution[hour]}
                          </span>
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height }}
                            transition={{ duration: 0.5, delay: hour * 0.015 }}
                            style={{
                              width: "100%",
                              borderRadius: "4px 4px 0 0",
                              background:
                                height === MAX_HOUR_BAR_HEIGHT
                                  ? "var(--color-brand-coral)"
                                  : "var(--color-brand-ochre)",
                              opacity: height > 0 ? 1 : 0.25,
                            }}
                            title={`${formatHourLabel(hour)}: ${echo.hourly_distribution[hour]} 次`}
                          />
                          <span
                            style={{
                              fontSize: 10,
                              color: "var(--color-muted)",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {hour % 3 === 0 ? formatHourLabel(hour) : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="panel-muted-text">
                    暂无播放时段数据，播放更多音乐后这里会显示 24 小时活跃分布。
                  </p>
                )}
              </motion.div>
            </section>
          </FadeIn>
        </>
      )}
    </div>
  );
};
