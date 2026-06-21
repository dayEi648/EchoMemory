import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { agentMonitorApi } from "../../shared/api/instances";
import type {
  AgentMonitorEvent,
  AgentMonitorRun,
  AgentMonitorRunDetail,
} from "../../shared/api/types";
import { getApiErrorMessage } from "../../shared/apiError";
import {
  AgentCursorPagination,
  AgentMonitorFilterPanel,
  AgentRunTable,
  type AgentMonitorFilters,
} from "./AgentMonitorListComponents";
import { AgentRunDetailModal } from "./AgentRunDetailModal";

const initialFilters: AgentMonitorFilters = {
  userId: "",
  status: "",
  model: "",
  startTime: "",
  endTime: "",
  query: "",
};

const toIsoDateTime = (value: string) =>
  value ? new Date(value).toISOString() : undefined;

export const AdminAIConversationMonitorPage = () => {
  const [draftFilters, setDraftFilters] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [runs, setRuns] = useState<AgentMonitorRun[]>([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursorHistory, setCursorHistory] = useState<(string | undefined)[]>([
    undefined,
  ]);
  const [pageIndex, setPageIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<AgentMonitorRunDetail | null>(null);
  const [events, setEvents] = useState<AgentMonitorEvent[]>([]);

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const result = await agentMonitorApi.listRuns({
        scenario: "ai_conversation",
        userId: filters.userId ? Number(filters.userId) : undefined,
        status: filters.status || undefined,
        model: filters.model || undefined,
        startTime: toIsoDateTime(filters.startTime),
        endTime: toIsoDateTime(filters.endTime),
        q: filters.query || undefined,
        cursor: cursorHistory[pageIndex],
        limit: 20,
      });
      setRuns(result.items);
      setTotal(result.total);
      setNextCursor(result.next_cursor);
    } catch (error) {
      toast.error(getApiErrorMessage(error, "加载 Agent 运行记录失败"));
    } finally {
      setLoading(false);
    }
  }, [cursorHistory, filters, pageIndex]);

  useEffect(() => {
    void loadRuns();
  }, [loadRuns]);

  const applyFilters = () => {
    setCursorHistory([undefined]);
    setPageIndex(0);
    setFilters(draftFilters);
  };

  const goNext = () => {
    if (!nextCursor) return;
    setCursorHistory((current) => [
      ...current.slice(0, pageIndex + 1),
      nextCursor,
    ]);
    setPageIndex((current) => current + 1);
  };

  const openDetail = async (runId: string) => {
    setDetailLoading(true);
    try {
      const [run, timeline] = await Promise.all([
        agentMonitorApi.getRun(runId),
        agentMonitorApi.listEvents(runId),
      ]);
      setDetail(run);
      setEvents(timeline);
    } catch (error) {
      toast.error(getApiErrorMessage(error, "加载运行详情失败"));
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <>
      <PaginatedPageLayout
        className="agent-monitor-page"
        header={
          <>
            <div className="admin-page-header">
              <div>
                <h1 className="page-title">AI 对话监控</h1>
                <p className="agent-monitor-subtitle">
                  查看每次对话 Graph 的提示词、消息、工具和记忆流转。
                </p>
              </div>
              <div className="agent-monitor-total">{total} 次运行</div>
            </div>
            <AgentMonitorFilterPanel
              filters={draftFilters}
              loading={loading}
              onChange={(key, value) =>
                setDraftFilters((current) => ({
                  ...current,
                  [key]: value,
                }))
              }
              onApply={applyFilters}
            />
          </>
        }
        footer={
          runs.length > 0 ? (
            <AgentCursorPagination
              pageIndex={pageIndex}
              hasNext={nextCursor !== null}
              loading={loading}
              onPrevious={() =>
                setPageIndex((current) => Math.max(0, current - 1))
              }
              onNext={goNext}
            />
          ) : undefined
        }
      >
        <AgentRunTable
          runs={runs}
          loading={loading}
          onOpenDetail={(runId) => void openDetail(runId)}
        />
      </PaginatedPageLayout>

      <AgentRunDetailModal
        run={detail}
        events={events}
        loading={detailLoading}
        onClose={() => {
          setDetail(null);
          setEvents([]);
        }}
      />
    </>
  );
};

