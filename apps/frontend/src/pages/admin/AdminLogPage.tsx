import { useEffect, useState, useCallback } from "react";
import { Search, ScrollText, AlertTriangle, AlertOctagon, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { logApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import type { SystemLogItem, SystemLogDetail, SystemLogLevel } from "../../shared/api/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";

const levelOptions: { value: string; label: string }[] = [
  { value: "", label: "全部等级" },
  { value: "WARNING", label: "WARNING" },
  { value: "ERROR", label: "ERROR" },
  { value: "CRITICAL", label: "CRITICAL" },
];

const levelIcon: Record<SystemLogLevel, typeof AlertTriangle> = {
  WARNING: AlertTriangle,
  ERROR: AlertOctagon,
  CRITICAL: ShieldAlert,
};

const levelClass: Record<SystemLogLevel, string> = {
  WARNING: "status-badge temp-ban",
  ERROR: "status-badge banned",
  CRITICAL: "status-badge deleted",
};

const fmtDate = (s: string | null): string => {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return s;
  return d.toLocaleString("zh-CN");
};

const truncate = (s: string | null, max = 80): string => {
  if (!s) return "—";
  return s.length > max ? `${s.slice(0, max)}...` : s;
};

const tryFormatJson = (s: string | null): string => {
  if (!s) return "—";
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
};

/** 详情弹窗中的信息块组件。 */
const DetailBlock = ({ label, value }: { label: string; value: React.ReactNode }) => (
  <div style={{ marginBottom: 16 }}>
    <div style={{ fontSize: 12, color: "var(--color-muted)", marginBottom: 6 }}>{label}</div>
    <div
      style={{
        fontSize: 13,
        background: "var(--color-surface-soft)",
        padding: "10px 12px",
        borderRadius: 8,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        maxHeight: 320,
        overflow: "auto",
        fontFamily: "monospace",
        lineHeight: 1.5,
      }}
    >
      {value}
    </div>
  </div>
);

export const AdminLogPage = () => {
  const [logs, setLogs] = useState<SystemLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [startTime, setStartTime] = useState<string>("");
  const [endTime, setEndTime] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(20);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<SystemLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const result = await logApi.adminListLogs({
        level: levelFilter || undefined,
        startTime: startTime || undefined,
        endTime: endTime || undefined,
        q: query || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      setLogs(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "加载日志失败"));
    } finally {
      setLoading(false);
    }
  }, [levelFilter, startTime, endTime, query, page, pageSize]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const handleSearch = () => setPage(0);

  const totalPages = Math.ceil(total / pageSize);

  const openDetail = async (log: SystemLogItem) => {
    setDetailLoading(true);
    try {
      const data = await logApi.adminGetLog(log.id);
      setDetail(data);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "加载日志详情失败"));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <>
      <PaginatedPageLayout
        header={(
          <>
            <FadeIn>
              <div className="admin-page-header">
                <h1 className="page-title">系统日志</h1>
              </div>
            </FadeIn>

            <FadeIn delay={0.08}>
              <div className="admin-search-row">
                <div className="admin-search-input-wrap">
                  <Search size={14} className="admin-search-icon" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="搜索日志消息关键词..."
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  />
                </div>

                <motion.button
                  className="primary-button"
                  onClick={handleSearch}
                  disabled={loading}
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  type="button"
                >
                  {loading ? "加载中" : "搜索"}
                </motion.button>
              </div>

              <div className="admin-filter-bar">
                <div className="admin-filter-field">
                  <select
                    value={levelFilter}
                    onChange={(e) => { setLevelFilter(e.target.value); setPage(0); }}
                  >
                    {levelOptions.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>

                <div className="admin-filter-field">
                  <input
                    type="datetime-local"
                    value={startTime}
                    onChange={(e) => { setStartTime(e.target.value); setPage(0); }}
                    placeholder="起始时间"
                    style={{ fontSize: 13 }}
                  />
                </div>

                <div className="admin-filter-field">
                  <input
                    type="datetime-local"
                    value={endTime}
                    onChange={(e) => { setEndTime(e.target.value); setPage(0); }}
                    placeholder="结束时间"
                    style={{ fontSize: 13 }}
                  />
                </div>
              </div>
            </FadeIn>
          </>
        )}
        footer={
          logs.length > 0 && (totalPages > 1 || total > 0) ? (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => { setPageSize(size); setPage(0); }}
              loading={loading}
              total={total}
            />
          ) : undefined
        }
      >
        {logs.length > 0 ? (
          <FadeIn delay={0.15}>
            <div className="admin-table-container">
              <div
                className="admin-table-header"
                style={{ gridTemplateColumns: "60px 160px 100px 1fr 140px auto" }}
              >
                <span>ID</span>
                <span>时间</span>
                <span>等级</span>
                <span>消息</span>
                <span>请求</span>
                <span>操作</span>
              </div>
              <StaggerContainer staggerDelay={0.03}>
                {logs.map((item) => {
                  const Icon = levelIcon[item.level];
                  return (
                    <StaggerItem key={item.id}>
                      <motion.div
                        className="admin-table-row"
                        style={{ gridTemplateColumns: "60px 160px 100px 1fr 140px auto", alignItems: "center" }}
                        whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                      >
                        <span style={{ fontSize: 12, color: "var(--color-muted)" }}>{item.id}</span>
                        <span style={{ fontSize: 12 }}>{fmtDate(item.created_at)}</span>
                        <span>
                          <span className={levelClass[item.level]} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                            <Icon size={12} />
                            {item.level}
                          </span>
                        </span>
                        <span
                          style={{
                            fontSize: 13,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={item.message}
                        >
                          {truncate(item.message, 60)}
                        </span>
                        <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
                          {item.request_method ? `${item.request_method} ${truncate(item.request_path, 20)}` : "—"}
                        </span>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          <motion.button
                            className="ghost-button"
                            onClick={() => openDetail(item)}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            type="button"
                            title="查看详情"
                            style={{ padding: "6px 8px", minHeight: "auto" }}
                          >
                            <ScrollText size={14} />
                          </motion.button>
                        </div>
                      </motion.div>
                    </StaggerItem>
                  );
                })}
              </StaggerContainer>
            </div>
          </FadeIn>
        ) : (
          <FadeIn delay={0.15}>
            <EmptyState
              icon={ScrollText}
              title="暂无日志"
              description="未找到符合条件的系统日志，请调整筛选条件或搜索关键词。"
            />
          </FadeIn>
        )}
      </PaginatedPageLayout>

      <Modal
        open={detailLoading || !!detail}
        onClose={() => setDetail(null)}
        title={detail ? `日志详情 #${detail.id}` : "加载中"}
        maxWidth={720}
      >
        {detail && (
          <div style={{ maxHeight: "70vh", overflow: "auto", paddingRight: 4 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 24px", marginBottom: 16 }}>
              <DetailBlock label="日志等级" value={detail.level} />
              <DetailBlock label="产生时间" value={fmtDate(detail.created_at)} />
              <DetailBlock label="Logger" value={detail.logger} />
              <DetailBlock
                label="请求"
                value={detail.request_method ? `${detail.request_method} ${detail.request_path}` : "—"}
              />
            </div>
            <DetailBlock label="消息" value={detail.message} />
            {detail.stack_trace && (
              <DetailBlock label="堆栈信息" value={detail.stack_trace} />
            )}
            {detail.request_body && (
              <DetailBlock label="请求体" value={tryFormatJson(detail.request_body)} />
            )}
            {detail.response_body && (
              <DetailBlock label="响应体" value={tryFormatJson(detail.response_body)} />
            )}
            {detail.extra && (
              <DetailBlock label="额外信息" value={tryFormatJson(detail.extra)} />
            )}
          </div>
        )}
      </Modal>
    </>
  );
};
