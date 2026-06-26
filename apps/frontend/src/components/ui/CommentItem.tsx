import { useState, useEffect, useRef } from "react";
import { ThumbsUp, ThumbsDown, MessageCircle, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { commentApi, appealApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import type { CommentItem as CommentItemType } from "../../shared/api/types";
import { formatRelativeTime } from "../../shared/utils";
import { Avatar } from "./Avatar";
import { ConfirmDeleteModal } from "./ConfirmDeleteModal";

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
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [likeCount, setLikeCount] = useState(comment.like_count);
  const [showReplies, setShowReplies] = useState(false);
  const [replies, setReplies] = useState<CommentItemType[]>([]);
  const [repliesLoading, setRepliesLoading] = useState(false);

  const isOwner = currentUserId === comment.user.id;
  const isRoot = comment.parent_id === null;
  const isNestedReply = comment.is_nested_reply;
  const isModerationDeleted =
    comment.is_deleted === true &&
    (comment.deletion_reason?.startsWith("MODERATION_") ?? false);
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
          setReplies(data.items);
          setShowReplies(true);
        }
      })
      .catch((err) => {
        if (!cancelled) toast.error(getApiErrorMessage(err, "加载回复失败"));
      });

    return () => {
      cancelled = true;
    };
  }, [replyRefreshKey, showReplies, isRoot, comment.id]);

  const handleLike = async () => {
    if (!liked && isOwner) {
      toast.info("不能给自己的评论点赞");
      return;
    }
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
        }
      }
    } catch (err) { toast.error(getApiErrorMessage(err, "操作失败")); }
  };

  const handleDislike = async () => {
    if (!disliked && isOwner) {
      toast.info("不能给自己的评论点踩");
      return;
    }
    try {
      if (disliked) {
        await commentApi.undislikeComment(comment.id);
        setDisliked(false);
      } else {
        await commentApi.dislikeComment(comment.id);
        setDisliked(true);
        if (liked) {
          setLiked(false);
          setLikeCount((count) => Math.max(0, count - 1));
        }
      }
    } catch (err) { toast.error(getApiErrorMessage(err, "操作失败")); }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await commentApi.deleteComment(comment.id);
      onDeleted(comment.id);
      toast.success("已删除");
      setDeleteOpen(false);
    } catch (err) { toast.error(getApiErrorMessage(err, "删除失败")); }
    finally { setDeleting(false); }
  };

  const loadReplies = async () => {
    if (showReplies) { setShowReplies(false); return; }
    setRepliesLoading(true);
    try {
      const data = await commentApi.listReplies(comment.id);
      setReplies(data.items);
      setShowReplies(true);
    } catch (err) { toast.error(getApiErrorMessage(err, "加载回复失败")); }
    finally { setRepliesLoading(false); }
  };

  const handleReplyDeleted = (replyId: number) => {
    setReplies((prev) => prev.filter((r) => r.id !== replyId));
  };

  const handleAppeal = async (c: CommentItemType) => {
    try {
      await appealApi.create({
        content_type: c.parent_id === null ? "comment" : "comment",
        content_id: c.id,
      });
      toast.success("申诉已提交");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "申诉失败"));
    }
  };

  return (
    <>
      <div
        className={[
          "comment-item",
          !isRoot ? "comment-item--reply" : "",
          isNestedReply ? "comment-item--nested-reply" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <div style={{ display: "flex", gap: 10 }}>
        <Avatar user={comment.user} size="sm" />
        <div className="comment-item-body">
          <div className="comment-item-meta">
            <span className="comment-item-author">{comment.user.nickname}</span>
            {comment.parent_user && (
              <span className="comment-item-reply-to">
                回复 <strong>@{comment.parent_user.nickname}</strong>
              </span>
            )}
            <span className="comment-item-time">{formatRelativeTime(comment.created_at)}</span>
          </div>
          {isModerationDeleted ? (
            <p
              className="comment-item-content"
              style={{
                color: "var(--color-muted-soft)",
                fontStyle: "italic",
              }}
            >
              此评论因违反社区准则已被隐藏
              {" · "}
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation();
                  void handleAppeal(comment);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.stopPropagation();
                }}
                style={{
                  color: "var(--color-brand-coral)",
                  cursor: "pointer",
                  fontStyle: "normal",
                  fontWeight: 500,
                  textDecoration: "underline",
                  textUnderlineOffset: 2,
                }}
              >
                申诉
              </span>
            </p>
          ) : (
            <p className="comment-item-content">{comment.content}</p>
          )}
          {!isModerationDeleted && (
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
              <button type="button" onClick={() => setDeleteOpen(true)} className="comment-action-btn">
                <Trash2 size={13} />
              </button>
            )}
          </div>
          )}

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

      <ConfirmDeleteModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => void handleDelete()}
        itemType="评论"
        itemName={comment.content.length > 30 ? comment.content.slice(0, 30) + "..." : comment.content}
        loading={deleting}
      />
    </>
  );
};
