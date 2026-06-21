import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Search,
  Workflow,
} from "lucide-react";

import { EmptyState } from "../../components/ui/EmptyState";
import type { AgentMonitorRun } from "../../shared/api/types";

export type AgentMonitorFilters = {
  userId: string;
  status: string;
  model: string;
  startTime: string;
  endTime: string;
  query: string;
};

const statusClass: Record<string, string> = {
  RUNNING: "status-badge temp-ban",
  SUCCEEDED: "status-badge active",
  FAILED: "status-badge banned",
  CANCELLED: "status-badge deleted",
};

const formatDate = (value: string) =>
  new Date(value).toLocaleString("zh-CN");

export const AgentMonitorFilterPanel = ({
  filters,
  loading,
  onChange,
  onApply,
}: {
  filters: AgentMonitorFilters;
  loading: boolean;
  onChange: (key: keyof AgentMonitorFilters, value: string) => void;
  onApply: () => void;
}) => (
  <>
    <div className="admin-search-row">
      <div className="admin-search-input-wrap">
        <Search size={14} className="admin-search-icon" />
        <input
          value={filters.query}
          onChange={(event) => onChange("query", event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && onApply()}
          placeholder="搜索用户、会话、模型或线程…"
          aria-label="搜索 Agent 运行"
        />
      </div>
      <button
        className="primary-button"
        type="button"
        onClick={onApply}
        disabled={loading}
      >
        {loading ? "加载中" : "查询"}
      </button>
    </div>
    <div className="admin-filter-bar agent-monitor-filters">
      <div className="admin-filter-field">
        <input
          type="number"
          min="1"
          value={filters.userId}
          onChange={(event) => onChange("userId", event.target.value)}
          placeholder="用户 ID"
          aria-label="用户 ID"
        />
      </div>
      <div className="admin-filter-field">
        <select
          value={filters.status}
          onChange={(event) => onChange("status", event.target.value)}
          aria-label="运行状态"
        >
          <option value="">全部状态</option>
          <option value="RUNNING">运行中</option>
          <option value="SUCCEEDED">成功</option>
          <option value="FAILED">失败</option>
          <option value="CANCELLED">已取消</option>
        </select>
      </div>
      <div className="admin-filter-field">
        <input
          value={filters.model}
          onChange={(event) => onChange("model", event.target.value)}
          placeholder="模型"
          aria-label="模型"
        />
      </div>
      <div className="admin-filter-field">
        <input
          type="datetime-local"
          value={filters.startTime}
          onChange={(event) => onChange("startTime", event.target.value)}
          aria-label="开始时间"
        />
      </div>
      <div className="admin-filter-field">
        <input
          type="datetime-local"
          value={filters.endTime}
          onChange={(event) => onChange("endTime", event.target.value)}
          aria-label="结束时间"
        />
      </div>
    </div>
  </>
);

export const AgentRunTable = ({
  runs,
  loading,
  onOpenDetail,
}: {
  runs: AgentMonitorRun[];
  loading: boolean;
  onOpenDetail: (runId: string) => void;
}) => {
  if (runs.length === 0) {
    return (
      <EmptyState
        icon={Bot}
        title={loading ? "正在加载" : "暂无 Agent 运行"}
        description={
          loading
            ? "正在读取 AI 对话监控记录。"
            : "当前筛选条件下没有 AI 对话运行记录。"
        }
      />
    );
  }

  return (
    <div className="admin-table-container agent-run-table">
      <div className="admin-table-header">
        <span>开始时间</span>
        <span>用户</span>
        <span>模型</span>
        <span>状态</span>
        <span>耗时</span>
        <span>Token</span>
        <span>工具</span>
        <span>操作</span>
      </div>
      {runs.map((run) => (
        <div className="admin-table-row" key={run.id}>
          <span>{formatDate(run.started_at)}</span>
          <span title={run.actor_username ?? undefined}>
            {run.actor_username ?? `#${run.actor_user_id ?? "—"}`}
          </span>
          <span title={run.model ?? undefined}>{run.model ?? "—"}</span>
          <span>
            <span className={statusClass[run.status]}>{run.status}</span>
          </span>
          <span>
            {run.duration_ms !== null ? `${run.duration_ms} ms` : "—"}
          </span>
          <span>{run.total_tokens ?? "—"}</span>
          <span>{run.tool_call_count}</span>
          <span>
            <button
              type="button"
              className="ghost-button"
              onClick={() => onOpenDetail(run.id)}
              aria-label={`查看运行 ${run.id} 详情`}
            >
              <Workflow size={15} /> 详情
            </button>
          </span>
        </div>
      ))}
    </div>
  );
};

export const AgentCursorPagination = ({
  pageIndex,
  hasNext,
  loading,
  onPrevious,
  onNext,
}: {
  pageIndex: number;
  hasNext: boolean;
  loading: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) => (
  <div className="agent-cursor-pagination">
    <button
      type="button"
      className="ghost-button"
      disabled={pageIndex === 0 || loading}
      onClick={onPrevious}
    >
      <ChevronLeft size={15} /> 上一页
    </button>
    <span>第 {pageIndex + 1} 页</span>
    <button
      type="button"
      className="ghost-button"
      disabled={!hasNext || loading}
      onClick={onNext}
    >
      下一页 <ChevronRight size={15} />
    </button>
  </div>
);

