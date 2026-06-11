import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { playlistApi } from "../../shared/api/instances";
import type { PlaylistListItem } from "../../shared/api/types";
import { Modal } from "./Modal";

interface CreatePlaylistModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (playlist: PlaylistListItem) => void;
}

export const CreatePlaylistModal = ({ open, onClose, onCreated }: CreatePlaylistModalProps) => {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setDescription("");
      setIsPrivate(false);
      setSubmitting(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast.error("请输入歌单名称");
      return;
    }

    setSubmitting(true);
    try {
      const created = await playlistApi.createPlaylist({
        title: trimmedTitle,
        description: description.trim() || undefined,
        is_private: isPrivate,
      });
      toast.success("歌单创建成功");
      onCreated?.({
        id: created.id,
        title: created.title,
        is_private: created.is_private,
        is_like: created.is_like,
        cover_icon_url: created.cover_icon_url,
        user: created.user,
        created_at: created.created_at,
      });
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建歌单失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="创建歌单"
      maxWidth={440}
      footer={
        <>
          <motion.button
            className="ghost-button"
            onClick={onClose}
            disabled={submitting}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            取消
          </motion.button>
          <motion.button
            className="btn-primary"
            onClick={() => void handleSubmit()}
            disabled={submitting}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            {submitting ? "创建中..." : "创建"}
          </motion.button>
        </>
      }
    >
      <div className="form-stack">
        <div className="form-field">
          <span className="form-field-label">
            歌单名称 <span style={{ color: "var(--color-danger)" }}>*</span>
          </span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="请输入歌单名称"
            autoFocus
            maxLength={128}
            onKeyDown={(e) => e.key === "Enter" && void handleSubmit()}
          />
        </div>
        <div className="form-field form-field--long">
          <span className="form-field-label">简介</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="选填"
            maxLength={500}
            rows={3}
          />
        </div>
        <label className="form-checkbox">
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(e) => setIsPrivate(e.target.checked)}
          />
          <span>设为私密歌单</span>
        </label>
      </div>
    </Modal>
  );
};
