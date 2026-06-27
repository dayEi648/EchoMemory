import { useEffect, useMemo, useState } from "react";
import {
  Users,
  Music,
  Album,
  MessageCircle,
  FileText,
  ListMusic,
  Play,
  Heart,
  Share2,
  Bot,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Flame,
  BarChart3,
  PieChart as PieChartIcon,
  Activity,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { EmptyState } from "../../components/ui/EmptyState";
import { userApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import type { DashboardStats } from "../../shared/api/types";

const COLORS = {
  lavender: "#b8a4ed",
  teal: "#1a3a3a",
  coral: "#ff6b5a",
  ochre: "#e8b94a",
  pink: "#ff4d8b",
  peach: "#ffb084",
  mint: "#a4d4c5",
  ink: "#0a0a0a",
  muted: "#6a6a6a",
  hairline: "#e5e5e5",
  surfaceCard: "#f5f0e0",
};

const CHART_COLORS = [
  COLORS.pink,
  COLORS.teal,
  COLORS.lavender,
  COLORS.ochre,
  COLORS.coral,
  COLORS.mint,
  COLORS.peach,
];

const statCards: {
  key: keyof DashboardStats;
  label: string;
  icon: React.ElementType;
  accent: "lavender" | "teal" | "coral" | "ochre" | "pink" | "peach";
}[] = [
  { key: "users", label: "注册用户", icon: Users, accent: "lavender" },
  { key: "music", label: "已上架音乐", icon: Music, accent: "teal" },
  { key: "albums", label: "专辑", icon: Album, accent: "coral" },
  { key: "playlists", label: "歌单", icon: ListMusic, accent: "ochre" },
  { key: "comments", label: "评论", icon: MessageCircle, accent: "pink" },
  { key: "space_posts", label: "空间动态", icon: FileText, accent: "peach" },
];

const formatNumber = (n: number) => n.toLocaleString("zh-CN");

const SkeletonCard = () => (
  <div className="dashboard-stat-card dashboard-stat-card--skeleton">
    <div className="stat-card-icon skeleton" />
    <div className="stat-value skeleton" style={{ width: 80, height: 28, marginBottom: 8 }} />
    <div className="stat-label skeleton" style={{ width: 60, height: 14 }} />
  </div>
);

const SkeletonChart = () => (
  <div className="dashboard-chart-card">
    <div className="dashboard-chart-header skeleton" style={{ width: 120, height: 18, marginBottom: 16 }} />
    <div className="dashboard-chart-body skeleton" style={{ width: "100%", height: 240, borderRadius: 12 }} />
  </div>
);

const SkeletonTable = () => (
  <div className="dashboard-chart-card">
    <div className="dashboard-chart-header skeleton" style={{ width: 120, height: 18, marginBottom: 16 }} />
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="skeleton" style={{ width: "100%", height: 40, marginBottom: 8, borderRadius: 8 }} />
    ))}
  </div>
);

export const AdminDashboardPage = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    userApi
      .adminGetStats()
      .then(setStats)
      .catch((err) => toast.error(getApiErrorMessage(err, "加载统计数据失败")))
      .finally(() => setLoading(false));
  }, []);

  const trendData = useMemo(() => {
    if (!stats) return [];
    return stats.content_trend.map((item) => ({
      ...item,
      date: item.date.slice(5),
    }));
  }, [stats]);

  const moderationData = useMemo(() => {
    if (!stats) return [];
    return [
      { name: "待审评论", value: stats.moderation_queue.pending_comments, color: COLORS.coral },
      { name: "待审动态", value: stats.moderation_queue.pending_space_posts, color: COLORS.ochre },
      { name: "审核任务", value: stats.moderation_queue.pending_moderation_tasks, color: COLORS.lavender },
    ];
  }, [stats]);

  const agentSuccessRate = useMemo(() => {
    if (!stats || stats.agent_run_summary.total_24h === 0) return 0;
    return Math.round(
      (stats.agent_run_summary.succeeded_24h / stats.agent_run_summary.total_24h) * 100,
    );
  }, [stats]);

  const totalModeration = useMemo(() => {
    if (!stats) return 0;
    return (
      stats.moderation_queue.pending_comments +
      stats.moderation_queue.pending_space_posts +
      stats.moderation_queue.pending_moderation_tasks
    );
  }, [stats]);

  return (
    <div className="admin-dashboard">
      <FadeIn>
        <h1 className="page-title">管理概览</h1>
      </FadeIn>

      {/* 顶部统计卡片 */}
      <StaggerContainer staggerDelay={0.06} className="admin-stats-grid">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => (
              <StaggerItem key={i}>
                <SkeletonCard />
              </StaggerItem>
            ))
          : statCards.map((card) => (
              <StaggerItem key={card.key}>
                <motion.div
                  className={`dashboard-stat-card dashboard-stat-card--${card.accent}`}
                  whileHover={{ y: -4, scale: 1.01 }}
                  transition={{ duration: 0.25 }}
                >
                  <motion.div
                    className="stat-card-icon"
                    whileHover={{ rotate: [0, -5, 5, 0] }}
                    transition={{ duration: 0.4 }}
                  >
                    <card.icon size={18} />
                  </motion.div>
                  <div className="stat-value">
                    {stats ? formatNumber(stats[card.key] as number) : "—"}
                  </div>
                  <div className="stat-label">{card.label}</div>
                </motion.div>
              </StaggerItem>
            ))}
      </StaggerContainer>

      {!loading && !stats && (
        <FadeIn>
          <EmptyState
            icon={AlertCircle}
            title="加载统计数据失败"
            description="请检查网络连接或稍后重试。"
          />
        </FadeIn>
      )}

      {/* 趋势 + 用户状态 */}
      <div className="dashboard-row">
        <FadeIn delay={0.2} className="dashboard-col dashboard-col--wide">
          {loading || !stats ? (
            <SkeletonChart />
          ) : trendData.length === 0 ? (
            <div className="dashboard-chart-card">
              <SectionHeader title="近 30 天内容增长" />
              <EmptyState icon={BarChart3} title="暂无趋势数据" compact />
            </div>
          ) : (
            <div className="dashboard-chart-card">
              <div className="dashboard-chart-header">
                <Activity size={18} />
                <span>近 30 天内容增长</span>
              </div>
              <div className="dashboard-chart-body">
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart data={trendData} margin={{ top: 10, right: 16, left: -16, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorUsers" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS.lavender} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={COLORS.lavender} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorMusic" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS.teal} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={COLORS.teal} stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorComments" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={COLORS.coral} stopOpacity={0.35} />
                        <stop offset="95%" stopColor={COLORS.coral} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke={COLORS.hairline} vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 11, fill: COLORS.muted }}
                      axisLine={{ stroke: COLORS.hairline }}
                      tickLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: COLORS.muted }}
                      axisLine={false}
                      tickLine={false}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#fffaf0",
                        border: `1px solid ${COLORS.hairline}`,
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                    <Area
                      type="monotone"
                      dataKey="users"
                      name="用户"
                      stroke={COLORS.lavender}
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorUsers)"
                    />
                    <Area
                      type="monotone"
                      dataKey="music"
                      name="音乐"
                      stroke={COLORS.teal}
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorMusic)"
                    />
                    <Area
                      type="monotone"
                      dataKey="comments"
                      name="评论"
                      stroke={COLORS.coral}
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorComments)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </FadeIn>

        <FadeIn delay={0.28} className="dashboard-col dashboard-col--narrow">
          {loading || !stats ? (
            <SkeletonChart />
          ) : stats.user_status_distribution.length === 0 ? (
            <div className="dashboard-chart-card">
              <SectionHeader title="用户状态分布" />
              <EmptyState icon={PieChartIcon} title="暂无数据" compact />
            </div>
          ) : (
            <div className="dashboard-chart-card">
              <div className="dashboard-chart-header">
                <PieChartIcon size={18} />
                <span>用户状态分布</span>
              </div>
              <div className="dashboard-chart-body">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={stats.user_status_distribution}
                      dataKey="count"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={3}
                    >
                      {stats.user_status_distribution.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#fffaf0",
                        border: `1px solid ${COLORS.hairline}`,
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </FadeIn>
      </div>

      {/* 审核队列 + 音乐风格 */}
      <div className="dashboard-row">
        <FadeIn delay={0.36} className="dashboard-col">
          {loading || !stats ? (
            <SkeletonChart />
          ) : totalModeration === 0 ? (
            <div className="dashboard-chart-card">
              <SectionHeader title="待审核队列" />
              <EmptyState icon={AlertCircle} title="暂无待审项目" compact />
            </div>
          ) : (
            <div className="dashboard-chart-card">
              <div className="dashboard-chart-header">
                <AlertCircle size={18} />
                <span>待审核队列</span>
                <span className="dashboard-chart-badge">{totalModeration}</span>
              </div>
              <div className="dashboard-chart-body">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={moderationData} layout="vertical" margin={{ left: 24, right: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={COLORS.hairline} horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 11, fill: COLORS.muted }} hide />
                    <YAxis
                      dataKey="name"
                      type="category"
                      tick={{ fontSize: 12, fill: COLORS.ink }}
                      axisLine={false}
                      tickLine={false}
                      width={70}
                    />
                    <Tooltip
                      cursor={{ fill: "transparent" }}
                      contentStyle={{
                        background: "#fffaf0",
                        border: `1px solid ${COLORS.hairline}`,
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="value" radius={[0, 8, 8, 0]} barSize={24}>
                      {moderationData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </FadeIn>

        <FadeIn delay={0.44} className="dashboard-col">
          {loading || !stats ? (
            <SkeletonChart />
          ) : stats.music_style_distribution.length === 0 ? (
            <div className="dashboard-chart-card">
              <SectionHeader title="音乐风格分布" />
              <EmptyState icon={PieChartIcon} title="暂无数据" compact />
            </div>
          ) : (
            <div className="dashboard-chart-card">
              <div className="dashboard-chart-header">
                <PieChartIcon size={18} />
                <span>音乐风格分布</span>
              </div>
              <div className="dashboard-chart-body">
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie
                      data={stats.music_style_distribution}
                      dataKey="count"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      paddingAngle={2}
                    >
                      {stats.music_style_distribution.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#fffaf0",
                        border: `1px solid ${COLORS.hairline}`,
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </FadeIn>
      </div>

      {/* 热度榜 + Agent / 互动 */}
      <div className="dashboard-row">
        <FadeIn delay={0.52} className="dashboard-col dashboard-col--wide">
          {loading || !stats ? (
            <SkeletonTable />
          ) : stats.top_hot_music.length === 0 ? (
            <div className="dashboard-chart-card">
              <SectionHeader title="热度榜 TOP5" />
              <EmptyState icon={Flame} title="暂无音乐数据" compact />
            </div>
          ) : (
            <div className="dashboard-chart-card">
              <div className="dashboard-chart-header">
                <Flame size={18} />
                <span>热度榜 TOP5</span>
              </div>
              <div className="dashboard-table-wrap">
                <table className="dashboard-table">
                  <thead>
                    <tr>
                      <th style={{ width: 50 }}>排名</th>
                      <th>音乐</th>
                      <th style={{ width: 90 }}>作者</th>
                      <th style={{ width: 80 }}>热度</th>
                      <th style={{ width: 90 }}>播放</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.top_hot_music.map((song, index) => (
                      <motion.tr
                        key={song.id}
                        initial={{ opacity: 0, x: -8 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.05 * index }}
                      >
                        <td>
                          <span
                            className={`dashboard-rank ${index < 3 ? "dashboard-rank--top" : ""}`}
                          >
                            {index + 1}
                          </span>
                        </td>
                        <td className="dashboard-table-title">{song.title}</td>
                        <td className="dashboard-table-muted">{song.authors}</td>
                        <td>
                          <span className="dashboard-hot-value">{song.hot}</span>
                        </td>
                        <td className="dashboard-table-muted">{formatNumber(song.play_count)}</td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </FadeIn>

        <FadeIn delay={0.6} className="dashboard-col dashboard-col--narrow dashboard-col--stack">
          {loading || !stats ? (
            <>
              <SkeletonChart />
              <SkeletonChart />
            </>
          ) : (
            <>
              <div className="dashboard-chart-card dashboard-mini-cards">
                <div className="dashboard-chart-header">
                  <Bot size={18} />
                  <span>Agent 运行（24h）</span>
                </div>
                <div className="dashboard-mini-grid">
                  <div className="dashboard-mini-card">
                    <Activity size={16} />
                    <div className="dashboard-mini-value">{stats.agent_run_summary.total_24h}</div>
                    <div className="dashboard-mini-label">总运行</div>
                  </div>
                  <div className="dashboard-mini-card">
                    <CheckCircle2 size={16} />
                    <div className="dashboard-mini-value">
                      {stats.agent_run_summary.succeeded_24h}
                    </div>
                    <div className="dashboard-mini-label">成功</div>
                  </div>
                  <div className="dashboard-mini-card">
                    <XCircle size={16} />
                    <div className="dashboard-mini-value">{stats.agent_run_summary.failed_24h}</div>
                    <div className="dashboard-mini-label">失败</div>
                  </div>
                  <div className="dashboard-mini-card dashboard-mini-card--wide">
                    <div className="dashboard-mini-label">成功率</div>
                    <div className="dashboard-mini-value">{agentSuccessRate}%</div>
                    <div className="dashboard-progress-bar">
                      <div
                        className="dashboard-progress-fill"
                        style={{ width: `${agentSuccessRate}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="dashboard-chart-card dashboard-mini-cards">
                <div className="dashboard-chart-header">
                  <Heart size={18} />
                  <span>全站互动总量</span>
                </div>
                <div className="dashboard-mini-grid">
                  <div className="dashboard-mini-card">
                    <Play size={16} />
                    <div className="dashboard-mini-value">
                      {formatNumber(stats.engagement_totals.total_plays)}
                    </div>
                    <div className="dashboard-mini-label">总播放</div>
                  </div>
                  <div className="dashboard-mini-card">
                    <Heart size={16} />
                    <div className="dashboard-mini-value">
                      {formatNumber(stats.engagement_totals.total_collections)}
                    </div>
                    <div className="dashboard-mini-label">总收藏</div>
                  </div>
                  <div className="dashboard-mini-card dashboard-mini-card--wide">
                    <Share2 size={16} />
                    <div className="dashboard-mini-value">
                      {formatNumber(stats.engagement_totals.total_forwards)}
                    </div>
                    <div className="dashboard-mini-label">总转发</div>
                  </div>
                </div>
              </div>
            </>
          )}
        </FadeIn>
      </div>

      <FadeIn delay={0.68}>
        <section>
          <div className="section-header">
            <h3>系统状态</h3>
          </div>
          <motion.div
            className="warm-panel"
            whileHover={{
              boxShadow: "0 4px 16px color-mix(in srgb, var(--color-brand-ochre) 12%, transparent)",
            }}
            transition={{ duration: 0.25 }}
          >
            <p className="panel-muted-text">
              热度定时维护每 4 小时执行一次；播放、收藏、评论时自动更新单首歌曲热度。
              转发功能已上线，用户可将音乐、专辑、歌单或他人动态转发至自己的空间。
              仪表盘数据每 5 分钟刷新一次缓存。
            </p>
          </motion.div>
        </section>
      </FadeIn>
    </div>
  );
};
