import { useCallback, useEffect, useState } from "react";
import {
  Eye,
  FileSearch,
  RefreshCw,
  RotateCcw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";

import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import {
  contentModerationApi,
} from "../../shared/api/instances";
import type { ModerationResource } from "../../shared/api/contentModerationApi";
import type {
  AdminModeratedContent,
  ManualModerationInput,
} from "../../shared/api/types";
import { getApiErrorMessage } from "../../shared/apiError";

type FilterState = {
  q: string;
  userId: string;
  targetType: string;
  targetId: string;
  safetyLevel: string;
  recommendationLevel: string;
  moderationStatus: string;
  deleted: string;
  recommended: string;
  startTime: string;
  endTime: string;
};

const initialFilters: FilterState = {
  q: "",
  userId: "",
  targetType: "",
  targetId: "",
  safetyLevel: "",
  recommendationLevel: "",
  moderationStatus: "",
  deleted: "",
  recommended: "",
  startTime: "",
  endTime: "",
};

const safetyLabels = {
  SAFE: "安全",
  RISKY: "风险",
  DANGEROUS: "危险",
} as const;

const statusLabels = {
  PENDING: "待审核",
  PROCESSING: "审核中",
  SUCCEEDED: "已审核",
  FAILED: "审核失败",
  MANUAL: "人工审核",
} as const;

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleString("zh-CN") : "—";

const toIso = (value: string) =>
  value ? new Date(value).toISOString() : undefined;

const parseBoolean = (value: string) =>
  value === "true" ? true : value === "false" ? false : undefined;

const Badge = ({
  tone,
  children,
}: {
  tone: string;
  children: React.ReactNode;
}) => <span className={`moderation-badge moderation-badge--${tone}`}>{children}</span>;

const DetailRow = ({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) => (
  <div className="moderation-detail-row">
    <span>{label}</span>
    <strong>{value}</strong>
  </div>
);

export const AdminContentModerationPage = ({
  resource,
  title,
}: {
  resource: ModerationResource;
  title: string;
}) => {
  const isComments = resource === "comments";
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [items, setItems] = useState<AdminModeratedContent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [detail, setDetail] = useState<AdminModeratedContent | null>(null);
  const [manualItem, setManualItem] =
    useState<AdminModeratedContent | null>(null);
  const [manualInput, setManualInput] = useState<ManualModerationInput>({
    safety_score: 10,
    recommendation_score: 0,
    reason: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await contentModerationApi.list(resource, {
        q: filters.q || undefined,
        userId: filters.userId ? Number(filters.userId) : undefined,
        targetType: isComments ? filters.targetType || undefined : undefined,
        targetId:
          isComments && filters.targetId
            ? Number(filters.targetId)
            : undefined,
        safetyLevel: filters.safetyLevel || undefined,
        recommendationLevel: filters.recommendationLevel || undefined,
        moderationStatus: filters.moderationStatus || undefined,
        isDeleted: parseBoolean(filters.deleted),
        isRecommended: parseBoolean(filters.recommended),
        startTime: toIso(filters.startTime),
        endTime: toIso(filters.endTime),
        limit: pageSize,
        offset: page * pageSize,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (error) {
      toast.error(getApiErrorMessage(error, `加载${title}失败`));
    } finally {
      setLoading(false);
    }
  }, [filters, isComments, page, pageSize, resource, title]);

  useEffect(() => {
    void load();
  }, [load]);

  const updateItem = (updated: AdminModeratedContent) => {
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
    setDetail((current) => (current?.id === updated.id ? updated : current));
  };

  const runAction = async (
    item: AdminModeratedContent,
    action: "rereview" | "restore",
  ) => {
    setActionId(item.id);
    try {
      const updated =
        action === "rereview"
          ? await contentModerationApi.rereview(resource, item.id)
          : await contentModerationApi.restore(resource, item.id);
      updateItem(updated);
      toast.success(action === "rereview" ? "已加入重新审核队列" : "内容已恢复");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "操作失败"));
    } finally {
      setActionId(null);
    }
  };

  const submitManualReview = async () => {
    if (!manualItem || !manualInput.reason.trim()) return;
    setActionId(manualItem.id);
    try {
      const updated = await contentModerationApi.manualReview(
        resource,
        manualItem.id,
        { ...manualInput, reason: manualInput.reason.trim() },
      );
      updateItem(updated);
      setManualItem(null);
      toast.success("人工审核结果已保存");
    } catch (error) {
      toast.error(getApiErrorMessage(error, "人工审核失败"));
    } finally {
      setActionId(null);
    }
  };

  const openManualReview = (item: AdminModeratedContent) => {
    setManualItem(item);
    setManualInput({
      safety_score: item.safety_score,
      recommendation_score: item.recommendation_score,
      reason: item.moderation_reason ?? "",
    });
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <PaginatedPageLayout
        header={
          <>
            <div className="admin-page-header">
              <div>
                <h1 className="page-title">{title}</h1>
                <p className="moderation-page-subtitle">
                  查询审核分值、档位、删除原因，并执行重新审核或人工复核。
                </p>
              </div>
              <span className="moderation-total">{total} 条内容</span>
            </div>

            <div className="admin-search-row">
              <div className="admin-search-input-wrap">
                <Search className="admin-search-icon" size={15} />
                <input
                  aria-label="搜索内容或用户"
                  value={draft.q}
                  onChange={(event) =>
                    setDraft((current) => ({
                      ...current,
                      q: event.target.value,
                    }))
                  }
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      setPage(0);
                      setFilters(draft);
                    }
                  }}
                  placeholder="搜索内容、用户名或昵称"
                />
              </div>
              <button
                className="primary-button"
                type="button"
                disabled={loading}
                onClick={() => {
                  setPage(0);
                  setFilters(draft);
                }}
              >
                <SlidersHorizontal size={15} />
                应用筛选
              </button>
            </div>

            <div className="admin-filter-bar moderation-filter-grid">
              <input
                aria-label="用户 ID"
                type="number"
                min={1}
                placeholder="用户 ID"
                value={draft.userId}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    userId: event.target.value,
                  }))
                }
              />
              {isComments && (
                <>
                  <select
                    aria-label="评论目标类型"
                    value={draft.targetType}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        targetType: event.target.value,
                      }))
                    }
                  >
                    <option value="">全部目标</option>
                    <option value="music">音乐</option>
                    <option value="playlist">歌单</option>
                    <option value="space_post">说说</option>
                  </select>
                  <input
                    aria-label="目标 ID"
                    type="number"
                    min={1}
                    placeholder="目标 ID"
                    value={draft.targetId}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        targetId: event.target.value,
                      }))
                    }
                  />
                </>
              )}
              <select
                aria-label="安全档位"
                value={draft.safetyLevel}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    safetyLevel: event.target.value,
                  }))
                }
              >
                <option value="">全部安全档位</option>
                <option value="SAFE">安全</option>
                <option value="RISKY">风险</option>
                <option value="DANGEROUS">危险</option>
              </select>
              <select
                aria-label="推荐档位"
                value={draft.recommendationLevel}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    recommendationLevel: event.target.value,
                  }))
                }
              >
                <option value="">全部推荐档位</option>
                <option value="NORMAL">普通</option>
                <option value="RECOMMENDED">推荐</option>
              </select>
              <select
                aria-label="审核状态"
                value={draft.moderationStatus}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    moderationStatus: event.target.value,
                  }))
                }
              >
                <option value="">全部审核状态</option>
                {Object.entries(statusLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <select
                aria-label="删除状态"
                value={draft.deleted}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    deleted: event.target.value,
                  }))
                }
              >
                <option value="">全部显示状态</option>
                <option value="false">正常显示</option>
                <option value="true">已逻辑删除</option>
              </select>
              <select
                aria-label="是否推荐"
                value={draft.recommended}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    recommended: event.target.value,
                  }))
                }
              >
                <option value="">全部推荐状态</option>
                <option value="true">已推荐</option>
                <option value="false">未推荐</option>
              </select>
              <input
                aria-label="开始时间"
                type="datetime-local"
                value={draft.startTime}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    startTime: event.target.value,
                  }))
                }
              />
              <input
                aria-label="结束时间"
                type="datetime-local"
                value={draft.endTime}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    endTime: event.target.value,
                  }))
                }
              />
            </div>
          </>
        }
        footer={
          total > 0 ? (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              loading={loading}
              total={total}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(0);
              }}
            />
          ) : undefined
        }
      >
        {items.length === 0 && !loading ? (
          <EmptyState
            icon={FileSearch}
            title="没有符合条件的内容"
            description="调整筛选条件后重新查询。"
            compact
          />
        ) : (
          <div className="admin-table-container moderation-table">
            <div className="admin-table-header moderation-table-grid">
              <span>内容</span>
              <span>用户</span>
              <span>安全</span>
              <span>推荐</span>
              <span>审核状态</span>
              <span>显示状态</span>
              <span>发表时间</span>
              <span>操作</span>
            </div>
            {items.map((item) => (
              <div key={item.id} className="admin-table-row moderation-table-grid">
                <div className="moderation-content-cell" title={item.content ?? ""}>
                  <strong>#{item.id}</strong>
                  <span>{item.content || "（仅图片或无附言）"}</span>
                </div>
                <span>@{item.username}<small>#{item.user_id}</small></span>
                <span>
                  {item.safety_level ? (
                    <Badge tone={item.safety_level.toLowerCase()}>
                      {safetyLabels[item.safety_level]} · {item.safety_score}
                    </Badge>
                  ) : "—"}
                </span>
                <span>
                  <Badge tone={item.is_recommended ? "recommended" : "normal"}>
                    {item.is_recommended ? "推荐" : "普通"} · {item.recommendation_score}
                  </Badge>
                </span>
                <span>
                  <Badge tone={item.moderation_status.toLowerCase()}>
                    {statusLabels[item.moderation_status]}
                  </Badge>
                </span>
                <span>
                  <Badge tone={item.is_deleted ? "deleted" : "visible"}>
                    {item.is_deleted ? "已删除" : "显示中"}
                  </Badge>
                </span>
                <span>{formatDate(item.created_at)}</span>
                <div className="moderation-actions">
                  <button
                    className="ghost-button"
                    type="button"
                    title="查看详情"
                    onClick={() => setDetail(item)}
                  >
                    <Eye size={15} />
                  </button>
                  <button
                    className="ghost-button"
                    type="button"
                    title="重新审核"
                    disabled={actionId === item.id}
                    onClick={() => void runAction(item, "rereview")}
                  >
                    <RefreshCw size={15} />
                  </button>
                  <button
                    className="ghost-button"
                    type="button"
                    title="人工审核"
                    disabled={actionId === item.id}
                    onClick={() => openManualReview(item)}
                  >
                    <SlidersHorizontal size={15} />
                  </button>
                  {item.is_deleted &&
                    item.deletion_reason?.startsWith("MODERATION_") && (
                      <button
                        className="ghost-button"
                        type="button"
                        title="恢复内容"
                        disabled={actionId === item.id}
                        onClick={() => void runAction(item, "restore")}
                      >
                        <RotateCcw size={15} />
                      </button>
                    )}
                </div>
              </div>
            ))}
          </div>
        )}
      </PaginatedPageLayout>

      <Modal
        open={detail !== null}
        onClose={() => setDetail(null)}
        title="审核详情"
        maxWidth={680}
      >
        {detail && (
          <div className="moderation-detail">
            <p className="moderation-detail-content">{detail.content || "（无文字内容）"}</p>
            <DetailRow label="内容 ID" value={detail.id} />
            <DetailRow label="发布用户" value={`@${detail.username} (#${detail.user_id})`} />
            {isComments && (
              <DetailRow
                label="评论目标"
                value={`${detail.target_type ?? "—"} #${detail.target_id ?? "—"}`}
              />
            )}
            <DetailRow label="安全分 / 档位" value={`${detail.safety_score} / ${detail.safety_level ? safetyLabels[detail.safety_level] : "—"}`} />
            <DetailRow label="推荐分 / 档位" value={`${detail.recommendation_score} / ${detail.is_recommended ? "推荐" : "普通"}`} />
            <DetailRow label="审核状态" value={statusLabels[detail.moderation_status]} />
            <DetailRow label="审核理由" value={detail.moderation_reason ?? "—"} />
            <DetailRow label="删除原因" value={detail.deletion_reason ?? "—"} />
            <DetailRow label="审核时间" value={formatDate(detail.moderated_at)} />
            <DetailRow label="发表时间" value={formatDate(detail.created_at)} />
          </div>
        )}
      </Modal>

      <Modal
        open={manualItem !== null}
        onClose={() => setManualItem(null)}
        title="人工审核"
        footer={
          <>
            <button className="ghost-button" type="button" onClick={() => setManualItem(null)}>
              取消
            </button>
            <button
              className="primary-button"
              type="button"
              disabled={!manualInput.reason.trim() || actionId !== null}
              onClick={() => void submitManualReview()}
            >
              保存审核结果
            </button>
          </>
        }
      >
        <div className="form-stack">
          <label>
            安全分（0–10）
            <input
              type="number"
              min={0}
              max={10}
              value={manualInput.safety_score}
              onChange={(event) =>
                setManualInput((current) => ({
                  ...current,
                  safety_score: Number(event.target.value),
                }))
              }
            />
          </label>
          <label>
            推荐分（0–10）
            <input
              type="number"
              min={0}
              max={10}
              value={manualInput.recommendation_score}
              onChange={(event) =>
                setManualInput((current) => ({
                  ...current,
                  recommendation_score: Number(event.target.value),
                }))
              }
            />
          </label>
          <label>
            审核理由
            <textarea
              rows={4}
              maxLength={1000}
              value={manualInput.reason}
              onChange={(event) =>
                setManualInput((current) => ({
                  ...current,
                  reason: event.target.value,
                }))
              }
            />
          </label>
          <p className="moderation-score-help">
            安全分：0–3 危险，4–6 风险，7–10 安全；推荐分达到 8 即标记推荐。
          </p>
        </div>
      </Modal>
    </>
  );
};
