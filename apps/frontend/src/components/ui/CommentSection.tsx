import { useState, useEffect, useCallback } from "react";
import { Send, MessageCircle } from "lucide-react";
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
}

export const CommentSection = ({ targetType, targetId }: CommentSectionProps) => {
  const { user } = useAuthStore();
  const currentUserId = user?.id ?? 0;

  const [comments, setComments] = useState<CommentItemType[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);

  // Input
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [replyTo, setReplyTo] = useState<{ parentId: number; rootId: number; nickname: string } | null>(null);

  const loadComments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await commentApi.listRootComments(targetType, targetId, {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      setComments(res.items);
      setTotal(res.total);
    } catch {
      toast.error("加载评论失败");
    } finally {
      setLoading(false);
    }
  }, [targetType, targetId, page]);

  useEffect(() => { loadComments(); }, [loadComments]);

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
      if (replyTo) {
        // Reply was added — reload to reflect new reply count on parent
        setReplyTo(null);
        loadComments();
      } else {
        // New root comment — prepend to list
        setComments((prev) => [created, ...prev]);
        setTotal((t) => t + 1);
      }
      setInput("");
      toast.success(replyTo ? "回复成功" : "评论成功");
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

  return (
    <div>
      {/* Input */}
      {user && (
        <div style={{ marginBottom: 20 }}>
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
                  onClick={() => setReplyTo(null)}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-accent)", fontSize: 12, padding: 0 }}
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
                background: submitting || !input.trim() ? "var(--color-primary-disabled)" : "var(--color-ink)",
                color: "white",
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

      {/* List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 32, color: "var(--color-muted)", fontSize: 13 }}>加载中...</div>
      ) : comments.length === 0 ? (
        <EmptyState icon={MessageCircle} title="暂无评论" description="快来发表第一条评论吧" compact />
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
            />
          ))}
          {(totalPages > 1 || total > 0) && (
            <PaginationBar page={page} totalPages={totalPages} onPageChange={setPage} loading={loading} total={total} />
          )}
        </>
      )}
    </div>
  );
};
