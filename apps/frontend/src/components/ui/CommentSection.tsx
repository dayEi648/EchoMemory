import { useState, useEffect, useCallback } from "react";
import { Send, MessageCircle, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { useAuthStore } from "../../shared/stores/authStore";
import { commentApi } from "../../shared/api/instances";
import type { CommentItem as CommentItemType, CommentTargetType } from "../../shared/api/types";
import { CommentItem } from "./CommentItem";
import { PaginationBar } from "./PaginationBar";
import { EmptyState } from "./EmptyState";

const PAGE_SIZE = 10;

interface CommentSectionProps {
  targetType: CommentTargetType;
  targetId: number;
  /** 已知评论总数，用于收起态展示；不传则轻量请求 */
  commentCount?: number;
  /** 嵌入模式：不显示收起栏，直接展示内容（如空间说说已有点击展开） */
  embedded?: boolean;
}

export const CommentSection = ({
  targetType,
  targetId,
  commentCount: commentCountProp,
  embedded = false,
}: CommentSectionProps) => {
  const { user } = useAuthStore();
  const currentUserId = user?.id ?? 0;

  const [expanded, setExpanded] = useState(embedded);
  const [comments, setComments] = useState<CommentItemType[]>([]);
  const [total, setTotal] = useState(commentCountProp ?? 0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [countLoading, setCountLoading] = useState(false);
  const [sortBy, setSortBy] = useState<string>("recommended");

  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [replyTo, setReplyTo] = useState<{ parentId: number; rootId: number; nickname: string } | null>(null);
  /** 根评论 id → 刷新序号，回复成功后递增以触发子回复列表重载 */
  const [replyRefreshKeys, setReplyRefreshKeys] = useState<Record<number, number>>({});

  useEffect(() => {
    if (commentCountProp !== undefined) {
      setTotal(commentCountProp);
    }
  }, [commentCountProp]);

  /** 收起态：仅拉取评论总数 */
  useEffect(() => {
    if (embedded || expanded || commentCountProp !== undefined) return;

    let cancelled = false;
    setCountLoading(true);
    commentApi
      .listRootComments(targetType, targetId, { limit: 1, offset: 0 })
      .then((res) => {
        if (!cancelled) setTotal(res.total);
      })
      .catch(() => {
        /* 收起态静默失败 */
      })
      .finally(() => {
        if (!cancelled) setCountLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [embedded, expanded, commentCountProp, targetType, targetId]);

  const loadComments = useCallback(async () => {
    if (!expanded) return;
    setLoading(true);
    try {
      const res = await commentApi.listRootComments(targetType, targetId, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        sort_by: sortBy,
      });
      setComments(res.items);
      setTotal(res.total);
    } catch {
      toast.error("加载评论失败");
    } finally {
      setLoading(false);
    }
  }, [targetType, targetId, page, expanded, sortBy]);

  useEffect(() => {
    loadComments();
  }, [loadComments]);

  const handleSubmit = async () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    setSubmitting(true);
    try {
      const created = await commentApi.createComment({
        target_type: targetType,
        target_id: targetId,
        content: trimmed,
        parent_id: replyTo?.parentId,
      });
      const wasReply = replyTo !== null;
      if (replyTo) {
        const { rootId } = replyTo;
        setReplyTo(null);
        setComments((prev) =>
          prev.map((c) => (c.id === rootId ? { ...c, reply_count: c.reply_count + 1 } : c)),
        );
        setReplyRefreshKeys((prev) => ({ ...prev, [rootId]: (prev[rootId] ?? 0) + 1 }));
      } else {
        setComments((prev) => [created, ...prev]);
        setTotal((t) => t + 1);
        if (page !== 0) {
          setPage(0);
        }
      }
      setInput("");
      toast.success(wasReply ? "回复成功" : "评论成功");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发表失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReply = (parentId: number, rootId: number) => {
    const parent = comments.find((c) => c.id === parentId);
    setReplyTo({ parentId, rootId, nickname: parent?.user.nickname ?? "用户" });
  };

  const handleDeleted = (commentId: number) => {
    setComments((prev) => prev.filter((c) => c.id !== commentId));
    setTotal((t) => Math.max(0, t - 1));
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const renderBody = () => (
    <>
      {comments.length > 0 && (
        <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
          {[
            { key: "recommended", label: "综合" },
            { key: "latest", label: "最新" },
            { key: "likes", label: "最热" },
          ].map((opt) => (
            <button
              key={opt.key}
              type="button"
              onClick={() => { setSortBy(opt.key); setPage(0); }}
              style={{
                padding: "4px 12px",
                borderRadius: 6,
                border: sortBy === opt.key ? "1px solid var(--color-ink)" : "1px solid var(--color-hairline)",
                background: sortBy === opt.key ? "var(--color-ink)" : "transparent",
                color: sortBy === opt.key ? "white" : "var(--color-muted)",
                fontSize: 12,
                fontWeight: sortBy === opt.key ? 600 : 400,
                cursor: "pointer",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {user && (
        <div style={{ marginTop: 16, marginBottom: 20 }}>
          <AnimatePresence>
            {replyTo && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                style={{
                  fontSize: 12,
                  color: "var(--color-muted)",
                  marginBottom: 6,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                回复 <strong>@{replyTo.nickname}</strong>
                <button
                  type="button"
                  onClick={() => setReplyTo(null)}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--color-accent)",
                    fontSize: 12,
                    padding: 0,
                  }}
                >
                  取消
                </button>
              </motion.div>
            )}
          </AnimatePresence>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={replyTo ? `回复 @${replyTo.nickname}...` : "写下你的评论..."}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSubmit()}
              maxLength={2000}
              style={{ flex: 1, fontSize: 14 }}
            />
            <motion.button
              onClick={handleSubmit}
              disabled={submitting || !input.trim()}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              type="button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                padding: "8px 16px",
                borderRadius: 10,
                border: "none",
                background: submitting || !input.trim() ? "var(--color-surface-soft)" : "var(--color-ink)",
                color: submitting || !input.trim() ? "var(--color-muted)" : "white",
                cursor: submitting || !input.trim() ? "not-allowed" : "pointer",
                fontSize: 13,
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              <Send size={14} />
              {submitting ? "发送中" : "发表"}
            </motion.button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 32, color: "var(--color-muted)", fontSize: 13 }}>
          加载中...
        </div>
      ) : comments.length === 0 ? (
        <EmptyState icon={MessageCircle} title="暂无评论" description="快来发表第一条评论吧" compact accent="lavender" />
      ) : (
        <>
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              currentUserId={currentUserId}
              targetType={targetType}
              targetId={targetId}
              onReply={handleReply}
              onDeleted={handleDeleted}
              replyRefreshKey={replyRefreshKeys[comment.id] ?? 0}
            />
          ))}
          <PaginationBar
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            loading={loading}
            total={total}
          />
        </>
      )}
    </>
  );

  if (embedded) {
    return <div>{renderBody()}</div>;
  }

  return (
    <div className="comment-section">
      <button
        type="button"
        className="comment-section-toggle"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <MessageCircle size={18} />
        <span>评论</span>
        <span className="comment-section-count">
          ({countLoading && commentCountProp === undefined ? "…" : total})
        </span>
        <span className="comment-section-toggle-icon">
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="comment-section-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
            style={{ overflow: "hidden" }}
          >
            {renderBody()}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
