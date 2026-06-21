import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  Database,
  MessageSquareText,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { Modal } from "../../components/ui/Modal";
import type {
  AgentMonitorEvent,
  AgentMonitorRunDetail,
} from "../../shared/api/types";

const eventIcons: Record<string, LucideIcon> = {
  llm: Bot,
  tool: Wrench,
  memory: Database,
  message: MessageSquareText,
  prompt: BrainCircuit,
};

const eventLabels: Record<string, string> = {
  "prompt.initialized": "系统提示词初始化",
  "prompt.rendered": "提示词渲染",
  "message.received": "收到用户消息",
  "tools.resolved": "解析可用工具",
  "llm.request.prepared": "模型请求已准备",
  "llm.response.completed": "模型响应完成",
  "memory.short_term.initialized": "短期记忆初始化",
  "memory.short_term.updated": "短期记忆更新",
  "memory.long_term.checked": "长期记忆检查",
  "memory.long_term.evaluated": "长期记忆评估",
  "memory.long_term.updated": "长期记忆更新",
  "chain.started": "执行单元开始",
  "chain.completed": "执行单元完成",
  "chain.failed": "执行单元失败",
  "llm.started": "模型调用开始",
  "llm.completed": "模型调用完成",
  "llm.failed": "模型调用失败",
  "tool.started": "工具调用开始",
  "tool.completed": "工具调用完成",
  "tool.failed": "工具调用失败",
};

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString("zh-CN") : "—";

const formatJson = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const DataBlock = ({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) => (
  <section className="agent-monitor-data-block">
    <h4>{label}</h4>
    <pre>{formatJson(value)}</pre>
  </section>
);

const EventTimelineItem = ({ event }: { event: AgentMonitorEvent }) => {
  const Icon =
    event.status === "FAILED"
      ? AlertTriangle
      : eventIcons[event.component_type] ?? BrainCircuit;
  return (
    <li className="agent-event">
      <div className={`agent-event__icon agent-event__icon--${event.status?.toLowerCase() ?? "neutral"}`}>
        <Icon size={15} />
      </div>
      <details open={event.status === "FAILED"}>
        <summary>
          <span className="agent-event__sequence">#{event.sequence}</span>
          <span className="agent-event__title">
            {eventLabels[event.event_type] ?? event.event_type}
          </span>
          <span className="agent-event__component">
            {event.component_name ?? event.component_type}
          </span>
          <span className="agent-event__time">
            {event.duration_ms !== null ? `${event.duration_ms} ms` : formatDate(event.occurred_at)}
          </span>
        </summary>
        <div className="agent-event__body">
          {event.payload !== null ? (
            <DataBlock label="事件数据" value={event.payload} />
          ) : null}
          {event.error !== null ? (
            <DataBlock label="错误" value={event.error} />
          ) : null}
          <div className="agent-event__meta">
            <span>时间：{formatDate(event.occurred_at)}</span>
            {event.framework_run_id ? (
              <span>Framework run：{event.framework_run_id}</span>
            ) : null}
          </div>
        </div>
      </details>
    </li>
  );
};

export const AgentRunDetailModal = ({
  run,
  events,
  loading,
  onClose,
}: {
  run: AgentMonitorRunDetail | null;
  events: AgentMonitorEvent[];
  loading: boolean;
  onClose: () => void;
}) => (
  <Modal
    open={loading || run !== null}
    onClose={onClose}
    title={run ? `Agent 运行 ${run.id.slice(0, 8)}` : "加载运行详情"}
    maxWidth={980}
  >
    {run ? (
      <div className="agent-run-detail">
        <div className="agent-run-summary">
          <div><span>用户</span><strong>{run.actor_username ?? `#${run.actor_user_id ?? "—"}`}</strong></div>
          <div><span>模型</span><strong>{run.model ?? "—"}</strong></div>
          <div><span>状态</span><strong>{run.status}</strong></div>
          <div><span>耗时</span><strong>{run.duration_ms !== null ? `${run.duration_ms} ms` : "—"}</strong></div>
          <div><span>Token</span><strong>{run.total_tokens ?? "—"}</strong></div>
          <div><span>工具调用</span><strong>{run.tool_call_count}</strong></div>
        </div>
        <div className="agent-run-payloads">
          <DataBlock label="运行输入" value={run.input} />
          <DataBlock label="运行输出" value={run.output} />
          {run.error !== null ? <DataBlock label="运行错误" value={run.error} /> : null}
        </div>
        <section>
          <div className="agent-timeline-heading">
            <h3>执行时间线</h3>
            <span>{events.length} 个事件</span>
          </div>
          <ol className="agent-event-list">
            {events.map((event) => (
              <EventTimelineItem key={event.id} event={event} />
            ))}
          </ol>
        </section>
      </div>
    ) : (
      <div className="agent-monitor-loading">正在加载运行详情…</div>
    )}
  </Modal>
);

