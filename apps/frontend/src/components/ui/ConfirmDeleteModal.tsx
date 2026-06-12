import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { Modal } from "./Modal";

interface ConfirmDeleteModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  /** 删除对象的类型名，如 "歌单"、"播放记录" */
  itemType: string;
  /** 删除对象的名称，如 "我的最爱" */
  itemName: string;
  /** 补充说明 */
  description?: string;
  loading?: boolean;
}

export const ConfirmDeleteModal = ({
  open,
  onClose,
  onConfirm,
  itemType,
  itemName,
  description,
  loading = false,
}: ConfirmDeleteModalProps) => {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`删除${itemType}`}
      maxWidth={400}
      footer={
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", width: "100%" }}>
          <motion.button
            className="ghost-button"
            onClick={onClose}
            disabled={loading}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            取消
          </motion.button>
          <motion.button
            className="btn-primary"
            onClick={onConfirm}
            disabled={loading}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ background: "var(--color-error)", color: "white" }}
          >
            {loading ? "删除中..." : "确认删除"}
          </motion.button>
        </div>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 12 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "color-mix(in srgb, var(--color-error) 12%, transparent)",
            color: "var(--color-error)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <AlertTriangle size={24} />
        </div>
        <div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--color-body)" }}>
            确定要删除{ itemType }
            <strong style={{ color: "var(--color-ink)" }}>「{itemName}」</strong>
            吗？
          </p>
          {description && (
            <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--color-muted)", lineHeight: 1.5 }}>
              {description}
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
};
