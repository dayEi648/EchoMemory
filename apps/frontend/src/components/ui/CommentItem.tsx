import { useState, useEffect, useRef } from "react";
import { ThumbsUp, ThumbsDown, MessageCircle, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { commentApi } from "../../shared/api/instances";
import type { CommentItem as CommentItemType } from "../../shared/api/types";
import { formatRelativeTime } from "../../shared/utils";
import { Avatar } from "./Avatar";

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
  /** 父级递增时刷新已展开的子回复列表 */
  replyRefreshKey?: number;
}

export const CommentItem = ({
  comment,
  currentUserId,
  targetType,
  targetId,
  onReply,
  onDeleted,
  replyRefreshKey = 0,
}: CommentItemProps) => {
  const [liked, setLiked] = useState(comment.liked_by_me ?? false);
  const [disliked, setDisliked] = useState(comment.disliked_by_me ?? false);
  const [likeCount, setLikeCount] = useState(comment.like_count);
  const [, setDislikeCount] = useState(comment.dislike_count);
  const [showReplies, setShowReplies] = useState(false);
  const [replies, setReplies] = useState<CommentItemType[]>([]);
  const [repliesLoading, setRepliesLoading] = useState(false);

  const isOwner = currentUserId === comment.user.id;
  const isRoot = comment.parent_id === null;
  const lastReplyRefreshKey = useRef(replyRefreshKey);

  useEffect(() => {
    if (!isRoot || !showReplies || replyRefreshKey === 0) {
      lastReplyRefreshKey.current = replyRefreshKey;
      return;
    }
    if (replyRefreshKey === lastReplyRefreshKey.current) return;
    lastReplyRefreshKey.current = replyRefreshKey;

    let cancelled = false;
    commentApi
      .listReplies(comment.id)
      .then((data) => {
        if (!cancelled) {
          setReplies(data);
          setShowReplies(true);
        }
      })
      .catch(() => {
        if (!cancelled) toast.error("加载回复失败");
      });

    return () => {
      cancelled = true;
    };
  }, [replyRefreshKey, showReplies, isRoot, comment.id]);

  const handleLike = async () => {
    try {
      if (liked) {
        await commentApi.unlikeComment(comment.id);
        setLiked(false);
        setLikeCount((count) => Math.max(0, count - 1));
      } else {
        await commentApi.likeComment(comment.id);
        setLiked(true);
        setLikeCount((count) => count + 1);
        if (disliked) {
          setDisliked(false);
          setDislikeCount((count) => Math.max(0, count - 1));
        }
      }
    } catch { toast.error("操作失败"); }
  };

  const handleDislike = async () => {
    try {
      if (disliked) {
        await commentApi.undislikeComment(comment.id);
        setDisliked(false);
        setDislikeCount((count) => Math.max(0, count - 1));
      } else {
        await commentApi.dislikeComment(comment.id);
        setDisliked(true);
        setDislikeCount((count) => count + 1);
        if (liked) {
          setLiked(false);
          setLikeCount((count) => Math.max(0, count - 1));
        }
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
    <div className={isRoot ? "comment-item" : "comment-item comment-item--reply"}>
      <div style={{ display: "flex", gap: 10 }}>
        <Avatar user={comment.user} size="sm" />
        <div className="comment-item-body">
          <div className="comment-item-meta">
            <span className="comment-item-author">{comment.user.nickname}</span>
            <span className="comment-item-time">{formatRelativeTime(comment.created_at)}</span>
          </div>
          <p className="comment-item-content">{comment.content}</p>
          <div className="comment-item-actions">
            <button
              type="button"
              onClick={handleLike}
              className={`comment-action-btn${liked ? " comment-action-btn--liked" : ""}`}
            >
              <ThumbsUp size={13} fill={liked ? "currentColor" : "none"} /> {likeCount || ""}
            </button>
            <button type="button" onClick={handleDislike} className="comment-action-btn">
              <ThumbsDown size={13} fill={disliked ? "currentColor" : "none"} />
            </button>
            <button
              type="button"
              onClick={() => onReply(comment.id, comment.root_id ?? comment.id)}
              className="comment-action-btn"
            >
              <MessageCircle size={13} /> 回复
            </button>
            {isOwner && (
              <button type="button" onClick={handleDelete} className="comment-action-btn">
                <Trash2 size={13} />
              </button>
            )}
          </div>

          {/* Replies expand */}
          {isRoot && comment.reply_count > 0 && (
            <button
              type="button"
              onClick={loadReplies}
              className="comment-action-btn"
              style={{ marginTop: 6, color: "var(--color-accent-2)", fontWeight: 500 }}
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
                className="comment-replies"
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
