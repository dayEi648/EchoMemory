import { useState } from "react";
import { Heart, MessageCircle, Trash2, Clock, Lock, ChevronDown, ChevronUp } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { Avatar } from "./Avatar";
import { CommentSection } from "./CommentSection";
import type { SpacePostListItem } from "../../shared/api/types";

export interface PostAuthor {
  id: number;
  nickname: string;
  username: string;
  avatar_url: string | null;
}

interface SpacePostCardProps {
  post: SpacePostListItem;
  author: PostAuthor;
  currentUserId: number;
  onDelete: (postId: number) => void;
  onLike: (postId: number) => void;
  onUnlike: (postId: number) => void;
}

function formatPostTime(dateStr: string): string {
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

export const SpacePostCard = ({
  post,
  author,
  currentUserId,
  onDelete,
  onLike,
  onUnlike,
}: SpacePostCardProps) => {
  const [liked, setLiked] = useState(post.liked_by_me ?? false);
  const [likeCount, setLikeCount] = useState(post.like_count ?? 0);
  const [deleting, setDeleting] = useState(false);
  const [showComments, setShowComments] = useState(false);

  const isOwner = currentUserId === author.id;
  const sortedImages = [...post.images].sort((a, b) => a.ordinal - b.ordinal);

  const handleLike = async () => {
    try {
      if (liked) {
        await onUnlike(post.id);
        setLiked(false);
        setLikeCount((count) => Math.max(0, count - 1));
      } else {
        await onLike(post.id);
        setLiked(true);
        setLikeCount((count) => count + 1);
      }
    } catch {
      toast.error("操作失败");
    }
  };

  const handleDelete = async () => {
    if (!confirm("确定删除这条说说吗？")) return;
    setDeleting(true);
    try {
      await onDelete(post.id);
      // parent handles removal from list
      toast.success("已删除");
    } catch {
      toast.error("删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const imageGridCols =
    sortedImages.length === 1 ? 1 : sortedImages.length <= 4 ? 2 : 3;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.25 }}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 14,
        padding: 20,
        opacity: deleting ? 0.5 : 1,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <Avatar
          user={{
            avatar_url: author.avatar_url,
            nickname: author.nickname,
            username: author.username,
          }}
          size="md"
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>{author.nickname}</span>
            {post.is_private && <Lock size={12} style={{ color: "var(--color-muted)" }} />}
          </div>
          <div style={{ fontSize: 12, color: "var(--color-muted)", display: "flex", alignItems: "center", gap: 4, marginTop: 2 }}>
            <Clock size={11} />
            {formatPostTime(post.created_at)}
          </div>
        </div>
      </div>

      {/* Content */}
      {post.content && (
        <p style={{ fontSize: 14, lineHeight: 1.7, margin: "0 0 12px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {post.content}
        </p>
      )}

      {/* Images */}
      {sortedImages.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${imageGridCols}, 1fr)`,
            gap: 6,
            marginBottom: 12,
          }}
        >
          {sortedImages.map((img, i) => (
            <div
              key={i}
              style={{
                aspectRatio: imageGridCols === 1 ? "16/9" : "1",
                borderRadius: 8,
                overflow: "hidden",
                background: "var(--color-border)",
              }}
            >
              <img
                src={img.image_url}
                alt={`图片 ${i + 1}`}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                loading="lazy"
              />
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", alignItems: "center", gap: 20, paddingTop: 4 }}>
        <motion.button
          className="ghost-button"
          onClick={handleLike}
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          type="button"
          title={liked ? "取消点赞" : "点赞"}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 13,
            padding: "4px 8px",
            minHeight: "auto",
            color: liked ? "var(--color-accent)" : "var(--color-muted)",
          }}
        >
          <Heart size={15} fill={liked ? "var(--color-accent)" : "none"} />
          赞{likeCount > 0 ? ` ${likeCount}` : ""}
        </motion.button>

        <motion.button
          onClick={() => setShowComments(!showComments)}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          type="button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 13,
            padding: "4px 8px",
            minHeight: "auto",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: showComments ? "var(--color-accent-2)" : "var(--color-muted)",
          }}
        >
          <MessageCircle size={14} />
          {post.comment_count}
          {showComments ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
        </motion.button>

        {isOwner && (
          <motion.button
            className="ghost-button"
            onClick={handleDelete}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            type="button"
            title="删除"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 13,
              padding: "4px 8px",
              minHeight: "auto",
              color: "var(--color-muted)",
              marginLeft: "auto",
            }}
          >
            <Trash2 size={14} />
            删除
          </motion.button>
        )}
      </div>

      {/* Comment Section */}
      {showComments && (
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--color-border)" }}>
          <CommentSection targetType="space_post" targetId={post.id} />
        </div>
      )}
    </motion.div>
  );
};
