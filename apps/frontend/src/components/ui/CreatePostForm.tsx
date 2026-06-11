import { useState, useRef } from "react";
import { Image, X, Send, Lock, Globe } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";

import { createSpacePostApi } from "../../shared/api/spacePostApi";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import type { SpacePostListItem } from "../../shared/api/types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const spacePostApi = createSpacePostApi({ baseUrl: API_BASE_URL, tokenStore });

const MAX_FILES = 9;
const MAX_CONTENT_LENGTH = 2000;

interface CreatePostFormProps {
  onCreated: (post: SpacePostListItem) => void;
}

export const CreatePostForm = ({ onCreated }: CreatePostFormProps) => {
  const [content, setContent] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [isPrivate, setIsPrivate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (!selectedFiles) return;
    const newFiles = Array.from(selectedFiles).slice(0, MAX_FILES - files.length);
    if (newFiles.length === 0) return;

    const updatedFiles = [...files, ...newFiles];
    setFiles(updatedFiles);

    const newPreviews = newFiles.map((f) => URL.createObjectURL(f));
    setPreviews((prev) => [...prev, ...newPreviews]);

    // Reset input so same file can be reselected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFile = (index: number) => {
    const updatedFiles = files.filter((_, i) => i !== index);
    const updatedPreviews = previews.filter((_, i) => i !== index);
    URL.revokeObjectURL(previews[index]);
    setFiles(updatedFiles);
    setPreviews(updatedPreviews);
  };

  const handleSubmit = async () => {
    const trimmed = content.trim();
    if (!trimmed && files.length === 0) {
      toast.error("请输入内容或上传图片");
      return;
    }
    if (trimmed.length > MAX_CONTENT_LENGTH) {
      toast.error(`内容不能超过 ${MAX_CONTENT_LENGTH} 字`);
      return;
    }

    setSubmitting(true);
    try {
      const created = await spacePostApi.createPost({
        content: trimmed || undefined,
        is_private: isPrivate,
        files: files.length > 0 ? files : undefined,
      });
      toast.success("发布成功");
      setContent("");
      setFiles([]);
      previews.forEach((p) => URL.revokeObjectURL(p));
      setPreviews([]);
      setIsPrivate(false);
      onCreated({
        id: created.id,
        user_id: created.user_id,
        content: created.content,
        is_private: created.is_private,
        comment_count: created.comment_count,
        images: created.images,
        created_at: created.created_at,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "发布失败");
    } finally {
      setSubmitting(false);
    }
  };

  const remaining = MAX_CONTENT_LENGTH - content.length;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 14,
        padding: 20,
        marginBottom: 24,
      }}
    >
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="分享你的音乐心情..."
        rows={3}
        style={{
          width: "100%",
          resize: "vertical",
          fontSize: 14,
          lineHeight: 1.6,
          border: "none",
          outline: "none",
          background: "transparent",
          color: "var(--color-ink)",
          fontFamily: "inherit",
        }}
      />

      {/* Image previews */}
      <AnimatePresence>
        {previews.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(80px, 1fr))",
              gap: 6,
              marginBottom: 12,
            }}
          >
            {previews.map((url, i) => (
              <div
                key={i}
                style={{
                  position: "relative",
                  aspectRatio: "1",
                  borderRadius: 8,
                  overflow: "hidden",
                  background: "var(--color-border)",
                }}
              >
                <img
                  src={url}
                  alt={`预览 ${i + 1}`}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
                <motion.button
                  onClick={() => removeFile(i)}
                  whileHover={{ scale: 1.15 }}
                  whileTap={{ scale: 0.85 }}
                  type="button"
                  style={{
                    position: "absolute",
                    top: 2,
                    right: 2,
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    background: "rgba(0,0,0,0.6)",
                    color: "white",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <X size={12} />
                </motion.button>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toolbar */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            style={{ display: "none" }}
            onChange={handleFileSelect}
          />
          <motion.button
            onClick={() => fileInputRef.current?.click()}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="button"
            title="上传图片"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              background: "transparent",
              cursor: "pointer",
              fontSize: 13,
              color: "var(--color-muted)",
            }}
          >
            <Image size={15} />
            图片 {files.length > 0 && `(${files.length}/${MAX_FILES})`}
          </motion.button>

          <motion.button
            onClick={() => setIsPrivate(!isPrivate)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="button"
            title={isPrivate ? "仅自己可见" : "公开可见"}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "6px 12px",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              background: isPrivate ? "var(--color-surface-soft)" : "transparent",
              cursor: "pointer",
              fontSize: 13,
              color: isPrivate ? "var(--color-ink)" : "var(--color-muted)",
            }}
          >
            {isPrivate ? <Lock size={14} /> : <Globe size={14} />}
            {isPrivate ? "私密" : "公开"}
          </motion.button>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: remaining < 50 ? "var(--color-danger)" : "var(--color-muted)" }}>
            {remaining}
          </span>
          <motion.button
            onClick={handleSubmit}
            disabled={submitting || (!content.trim() && files.length === 0)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "8px 18px",
              borderRadius: 10,
              border: "none",
              background:
                submitting || (!content.trim() && files.length === 0)
                  ? "var(--color-primary-disabled)"
                  : "var(--color-ink)",
              color: "white",
              cursor:
                submitting || (!content.trim() && files.length === 0) ? "not-allowed" : "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            <Send size={14} />
            {submitting ? "发布中" : "发布"}
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
};
