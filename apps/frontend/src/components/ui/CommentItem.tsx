import { useState } from "react";
import { ThumbsUp, ThumbsDown, MessageCircle, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { createCommentApi } from "../../shared/api/commentApi";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import type { CommentItem as CommentItemType } from "../../shared/api/types";
import { Avatar } from "./Avatar";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const commentApi = createCommentApi({ baseUrl: API_BASE_URL, tokenStore });

interface CommentItemProps {
  comment: CommentItemType;
  currentUserId: number;
  /** 回复用的 target 信息 */
  targetType: string;
  targetId: number;
  /** 直接回复当前评论 */
  onReply: (parentId: number, rootId: number) => void;
  /** 被删除回调 */
  onDeleted: (commentId: number) => void;
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export const CommentItem = ({ comment, currentUserId, targetType, targetId, onReply, onDeleted }: CommentItemProps) => {
  const [liked, setLiked] = useState(false);
  const [disliked, setDisliked] = useState(false);
  const [showReplies, setShowReplies] = useState(false);
  const [replies, setReplies] = useState<CommentItemType[]>([]);
  const [repliesLoading, setRepliesLoading] = useState(false);

  const isOwner = currentUserId === comment.user.id;
  const isRoot = comment.parent_id === null;

  const handleLike = async () => {
    try {
      if (liked) {
        await commentApi.unlikeComment(comment.id);
        setLiked(false);
      } else {
        await commentApi.likeComment(comment.id);
        setLiked(true);
        if (disliked) setDisliked(false);
      }
    } catch { toast.error("操作失败"); }
  };

  const handleDislike = async () => {
    try {
      if (disliked) {
        await commentApi.undislikeComment(comment.id);
        setDisliked(false);
      } else {
        await commentApi.dislikeComment(comment.id);
        setDisliked(true);
        if (liked) setLiked(false);
      }
    } catch { toast.error("操作失败"); }
  };

  const handleDelete = async () => {
    if (!confirm("确定删除这条评论吗？")) return;
    try {
      await commentApi.deleteComment(comment.id);
      onDeleted(comment.id);
      toast.success("已删除");
    } catch { toast.error("删除失败"); }
  };

  const loadReplies = async () => {
    if (showReplies) { setShowReplies(false); return; }
    setRepliesLoading(true);
    try {
      const data = await commentApi.listReplies(comment.id);
      setReplies(data);
      setShowReplies(true);
    } catch { toast.error("加载回复失败"); }
    finally { setRepliesLoading(false); }
  };

  const handleReplyDeleted = (replyId: number) => {
    setReplies((prev) => prev.filter((r) => r.id !== replyId));
  };

  return (
    <div style={{ marginBottom: isRoot ? 16 : 8 }}>
      <div style={{ display: "flex", gap: 10 }}>
        <Avatar user={comment.user} size="sm" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>{comment.user.nickname}</span>
            <span style={{ fontSize: 11, color: "var(--color-muted)" }}>{formatTime(comment.created_at)}</span>
          </div>
          <p style={{ fontSize: 14, lineHeight: 1.6, margin: "0 0 8px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
            {comment.content}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <button onClick={handleLike} style={{ ...actionBtnStyle, color: liked ? "var(--color-accent)" : "var(--color-muted)" }}>
              <ThumbsUp size={13} fill={liked ? "var(--color-accent)" : "none"} /> {comment.like_count || ""}
            </button>
            <button onClick={handleDislike} style={{ ...actionBtnStyle, color: disliked ? "var(--color-ink)" : "var(--color-muted)" }}>
              <ThumbsDown size={13} fill={disliked ? "var(--color-ink)" : "none"} />
            </button>
            <button onClick={() => onReply(comment.id, comment.root_id ?? comment.id)} style={actionBtnStyle}>
              <MessageCircle size={13} /> 回复
            </button>
            {isOwner && (
              <button onClick={handleDelete} style={{ ...actionBtnStyle, color: "var(--color-muted)" }}>
                <Trash2 size={13} />
              </button>
            )}
          </div>

          {/* Replies expand */}
          {isRoot && comment.reply_count > 0 && (
            <button
              onClick={loadReplies}
              style={{
                ...actionBtnStyle,
                marginTop: 6,
                color: "var(--color-accent-2)",
                fontWeight: 500,
              }}
            >
              {repliesLoading ? "加载中..." : showReplies ? <><ChevronUp size={13} /> 收起回复</> : <><ChevronDown size={13} /> {comment.reply_count} 条回复</>}
            </button>
          )}

          {/* Nested replies */}
          <AnimatePresence>
            {showReplies && replies.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                style={{ marginTop: 8, paddingLeft: 16, borderLeft: "2px solid var(--color-border)" }}
              >
                {replies.map((reply) => (
                  <CommentItem
                    key={reply.id}
                    comment={reply}
                    currentUserId={currentUserId}
                    targetType={targetType}
                    targetId={targetId}
                    onReply={onReply}
                    onDeleted={handleReplyDeleted}
                  />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

const actionBtnStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  cursor: "pointer",
  padding: "2px 4px",
  fontSize: 12,
  display: "inline-flex",
  alignItems: "center",
  gap: 3,
  color: "var(--color-muted)",
};
