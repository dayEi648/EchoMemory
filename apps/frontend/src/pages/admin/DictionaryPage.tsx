import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Plus, Pencil, Trash2, BookOpen, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

import { createDictionaryApi } from "../../shared/api/dictionaryApi";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import type { DictionaryType, DictionaryItem } from "../../shared/api/types";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const dictionaryApi = createDictionaryApi({ baseUrl: API_BASE_URL, tokenStore });

const DICT_TYPES: { key: DictionaryType; label: string }[] = [
  { key: "styles", label: "风格" },
  { key: "languages", label: "语言" },
  { key: "instruments", label: "乐器" },
  { key: "emotion_tags", label: "情感标签" },
  { key: "interest_tags", label: "兴趣标签" },
];

export const DictionaryPage = () => {
  const [activeType, setActiveType] = useState<DictionaryType>("styles");
  const [items, setItems] = useState<DictionaryItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Modal 状态
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<DictionaryItem | null>(null);
  const [deletingItem, setDeletingItem] = useState<DictionaryItem | null>(null);
  const [formName, setFormName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadItems = async (type: DictionaryType) => {
    setLoading(true);
    try {
      const data = await dictionaryApi.listDictionary(type);
      setItems(data);
    } catch {
      toast.error("加载字典数据失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems(activeType);
  }, [activeType]);

  const handleCreate = async () => {
    const name = formName.trim();
    if (!name) {
      toast.error("名称不能为空");
      return;
    }
    setSubmitting(true);
    try {
      const created = await dictionaryApi.createDictionaryItem(activeType, { name });
      setItems((prev) => [...prev, created]);
      toast.success("创建成功");
      setIsCreateOpen(false);
      setFormName("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  const openEdit = (item: DictionaryItem) => {
    setEditingItem(item);
    setFormName(item.name);
    setIsEditOpen(true);
  };

  const handleEdit = async () => {
    if (!editingItem) return;
    const name = formName.trim();
    if (!name) {
      toast.error("名称不能为空");
      return;
    }
    setSubmitting(true);
    try {
      const updated = await dictionaryApi.updateDictionaryItem(activeType, editingItem.id, { name });
      setItems((prev) =>
        prev.map((i) => (i.id === updated.id ? updated : i)),
      );
      toast.success("更新成功");
      setIsEditOpen(false);
      setEditingItem(null);
      setFormName("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新失败");
    } finally {
      setSubmitting(false);
    }
  };

  const openDelete = (item: DictionaryItem) => {
    setDeletingItem(item);
    setIsDeleteOpen(true);
  };

  const handleDelete = async () => {
    if (!deletingItem) return;
    setSubmitting(true);
    try {
      await dictionaryApi.deleteDictionaryItem(activeType, deletingItem.id);
      setItems((prev) => prev.filter((i) => i.id !== deletingItem.id));
      toast.success("删除成功");
      setIsDeleteOpen(false);
      setDeletingItem(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("409") || msg.includes("Conflict")) {
        toast.error("该字典项已被业务数据引用，无法删除");
      } else {
        toast.error(msg || "删除失败");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const activeLabel = DICT_TYPES.find((d) => d.key === activeType)?.label ?? "";

  return (
    <div>
      <FadeIn>
        <h1 className="page-title">字典维护</h1>
      </FadeIn>

      {/* 字典类型切换 */}
      <FadeIn delay={0.06}>
        <div
          style={{
            display: "flex",
            gap: 8,
            marginBottom: 20,
            flexWrap: "wrap",
          }}
        >
          {DICT_TYPES.map((t) => {
            const isActive = activeType === t.key;
            return (
              <motion.button
                key={t.key}
                onClick={() => setActiveType(t.key)}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                type="button"
                style={{
                  padding: "8px 16px",
                  borderRadius: 20,
                  fontSize: 13,
                  fontWeight: 500,
                  border: "none",
                  cursor: "pointer",
                  background: isActive ? "var(--color-ink)" : "var(--color-border)",
                  color: isActive ? "white" : "var(--color-ink)",
                  transition: "background 0.15s, color 0.15s",
                }}
              >
                {t.label}
              </motion.button>
            );
          })}
        </div>
      </FadeIn>

      {/* 工具栏 */}
      <FadeIn delay={0.1}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <span style={{ fontSize: 14, color: "var(--color-muted)", fontWeight: 500 }}>
            {activeLabel} · 共 {items.length} 项
          </span>
          <motion.button
            className="btn-primary"
            onClick={() => {
              setFormName("");
              setIsCreateOpen(true);
            }}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Plus size={14} />
            新增
          </motion.button>
        </div>
      </FadeIn>

      {/* 表格 */}
      {items.length > 0 ? (
        <FadeIn delay={0.14}>
          <div className="admin-table-container">
            <div
              className="admin-table-header"
              style={{ gridTemplateColumns: "60px 1fr auto" }}
            >
              <span>ID</span>
              <span>名称</span>
              <span>操作</span>
            </div>
            <StaggerContainer staggerDelay={0.02}>
              {items.map((item) => (
                <StaggerItem key={item.id}>
                  <motion.div
                    className="admin-table-row"
                    style={{ gridTemplateColumns: "60px 1fr auto" }}
                    whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                  >
                    <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
                      {item.id}
                    </span>
                    <span style={{ fontWeight: 500 }}>{item.name}</span>
                    <div style={{ display: "flex", gap: 6 }}>
                      <motion.button
                        className="ghost-button"
                        onClick={() => openEdit(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="编辑"
                        style={{ padding: "6px 8px", minHeight: "auto" }}
                      >
                        <Pencil size={14} />
                      </motion.button>
                      <motion.button
                        className="ghost-button"
                        onClick={() => openDelete(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="删除"
                        style={{
                          padding: "6px 8px",
                          minHeight: "auto",
                          color: "var(--color-danger)",
                        }}
                      >
                        <Trash2 size={14} />
                      </motion.button>
                    </div>
                  </motion.div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>
        </FadeIn>
      ) : loading ? (
        <div className="loading-screen" style={{ height: "30vh" }}>
          <div style={{ fontSize: 14, fontWeight: 500 }}>加载中...</div>
        </div>
      ) : (
        <FadeIn delay={0.14}>
          <EmptyState
            icon={BookOpen}
            title={`暂无${activeLabel}数据`}
            description="点击右上角按钮添加第一条字典项。"
          />
        </FadeIn>
      )}

      {/* 新增弹窗 */}
      <Modal
        open={isCreateOpen}
        onClose={() => {
          setIsCreateOpen(false);
          setFormName("");
        }}
        title={`新增${activeLabel}`}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => {
                setIsCreateOpen(false);
                setFormName("");
              }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="btn-primary"
              onClick={handleCreate}
              disabled={submitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {submitting ? "保存中..." : "确认新增"}
            </motion.button>
          </>
        }
      >
        <div className="form-stack">
          <label>
            名称 <span style={{ color: "var(--color-danger)" }}>*</span>
            <input
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder={`请输入${activeLabel}名称`}
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
            />
          </label>
        </div>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        open={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setEditingItem(null);
          setFormName("");
        }}
        title={`编辑${activeLabel}`}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => {
                setIsEditOpen(false);
                setEditingItem(null);
                setFormName("");
              }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="btn-primary"
              onClick={handleEdit}
              disabled={submitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {submitting ? "保存中..." : "确认修改"}
            </motion.button>
          </>
        }
      >
        <div className="form-stack">
          <label>
            名称 <span style={{ color: "var(--color-danger)" }}>*</span>
            <input
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder={`请输入${activeLabel}名称`}
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleEdit()}
            />
          </label>
        </div>
      </Modal>

      {/* 删除确认弹窗 */}
      <Modal
        open={isDeleteOpen}
        onClose={() => {
          setIsDeleteOpen(false);
          setDeletingItem(null);
        }}
        title={`删除${activeLabel}`}
        maxWidth={420}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => {
                setIsDeleteOpen(false);
                setDeletingItem(null);
              }}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="danger-button"
              onClick={handleDelete}
              disabled={submitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {submitting ? "删除中..." : "确认删除"}
            </motion.button>
          </>
        }
      >
        <div className="form-stack">
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 14px",
              background: "rgba(229, 72, 77, 0.08)",
              borderRadius: 10,
              border: "1px solid rgba(229, 72, 77, 0.2)",
            }}
          >
            <AlertTriangle size={20} style={{ color: "var(--color-danger)", flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: "var(--color-danger)" }}>
              若该字典项已被业务数据引用，删除将失败。
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-muted)" }}>
            确定要删除 <strong>"{deletingItem?.name}"</strong> 吗？
          </p>
        </div>
      </Modal>
    </div>
  );
};
