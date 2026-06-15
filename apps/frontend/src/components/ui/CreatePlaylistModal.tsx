import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";

import { playlistApi } from "../../shared/api/instances";
import type { PlaylistListItem } from "../../shared/api/types";
import { Modal } from "./Modal";
import { ConfirmDeleteModal } from "./ConfirmDeleteModal";
import { getApiErrorMessage } from "../../shared/apiError";

interface CreatePlaylistModalProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (playlist: PlaylistListItem) => void;
  /** 编辑模式：传入现有歌单数据（id + 当前值）。不传则为创建模式。 */
  edit?: {
    id: number;
    title: string;
    description: string | null;
    is_private: boolean;
  };
  /** 编辑成功后回调（传入更新后的简要信息）。 */
  onUpdated?: (playlist: PlaylistListItem) => void;
  /** 删除成功后回调。 */
  onDeleted?: (playlistId: number) => void;
}

export const CreatePlaylistModal = ({
  open,
  onClose,
  onCreated,
  edit,
  onUpdated,
  onDeleted,
}: CreatePlaylistModalProps) => {
  const isEdit = !!edit;

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!open) {
      setTitle("");
      setDescription("");
      setIsPrivate(false);
      setSubmitting(false);
      setDeleteModalOpen(false);
      setDeleting(false);
    } else if (edit) {
      setTitle(edit.title);
      setDescription(edit.description ?? "");
      setIsPrivate(edit.is_private);
      setDeleteModalOpen(false);
      setDeleting(false);
    }
  }, [open, edit]);

  const handleSubmit = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      toast.error("请输入歌单名称");
      return;
    }

    setSubmitting(true);
    try {
      if (isEdit) {
        const updated = await playlistApi.updatePlaylist(edit!.id, {
          title: trimmedTitle,
          description: description.trim() || undefined,
          is_private: isPrivate,
        });
        toast.success("歌单已更新");
        onUpdated?.({
          id: updated.id,
          title: updated.title,
          is_private: updated.is_private,
          is_like: updated.is_like,
          cover_icon_url: updated.cover_icon_url,
          user: updated.user,
          created_at: updated.created_at,
        });
      } else {
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
      }
      onClose();
    } catch (err) {
      toast.error(getApiErrorMessage(err, isEdit ? "更新失败" : "创建失败"));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!edit) return;
    setDeleting(true);
    try {
      await playlistApi.deletePlaylist(edit.id);
      toast.success("歌单已删除");
      onDeleted?.(edit.id);
      setDeleteModalOpen(false);
      onClose();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除失败"));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={isEdit ? "编辑歌单" : "创建歌单"}
        maxWidth={440}
        footer={
          <div style={{ display: "flex", gap: 10, width: "100%", justifyContent: isEdit ? "space-between" : "flex-end" }}>
            {isEdit && (
              <motion.button
                className="danger-button"
                onClick={() => setDeleteModalOpen(true)}
                disabled={submitting}
                whileTap={{ scale: 0.97 }}
                type="button"
                style={{ minHeight: 36, padding: "0 14px" }}
              >
                删除歌单
              </motion.button>
            )}
            <div style={{ display: "flex", gap: 10 }}>
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
                {submitting ? (isEdit ? "保存中..." : "创建中...") : isEdit ? "保存" : "创建"}
              </motion.button>
            </div>
          </div>
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

      {/* 删除确认弹窗（覆盖在编辑弹窗之上） */}
      <ConfirmDeleteModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={() => void handleDeleteConfirm()}
        itemType="歌单"
        itemName={edit?.title ?? ""}
        description="删除后无法恢复，歌单中的歌曲不会被删除。"
        loading={deleting}
      />
    </>
  );
};
