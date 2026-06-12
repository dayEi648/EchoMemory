import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Image, Plus, Pencil, Trash2, GripVertical, Search } from "lucide-react";

import { carouselApi, musicApi, albumApi } from "../../shared/api/instances";
import type { CarouselItem, CarouselCreateInput } from "../../shared/api/carouselApi";
import type { MusicListItem, AlbumListItem } from "../../shared/api/types";
import { PageTitle } from "../../components/ui/PageTitle";
import { FadeIn } from "../../components/motion/FadeIn";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { ConfirmDeleteModal } from "../../components/ui/ConfirmDeleteModal";

type SearchTarget = { id: number; title: string } | null;

export const AdminCarouselPage = () => {
  const [items, setItems] = useState<CarouselItem[]>([]);
  const [loading, setLoading] = useState(true);

  // 创建/编辑弹窗
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CarouselItem | null>(null);
  const [formType, setFormType] = useState<"music" | "album">("music");
  const [formTitle, setFormTitle] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [searchResults, setSearchResults] = useState<(MusicListItem | AlbumListItem)[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<SearchTarget>(null);
  const [submitting, setSubmitting] = useState(false);

  // 删除确认
  const [deleteTarget, setDeleteTarget] = useState<CarouselItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadItems = useCallback(async () => {
    try {
      const data = await carouselApi.listCarousel();
      setItems(data);
    } catch {
      toast.error("加载推图列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  // 模糊搜索音乐或专辑
  const handleSearch = async () => {
    const q = searchQ.trim();
    if (!q) { setSearchResults([]); return; }
    try {
      if (formType === "music") {
        const res = await musicApi.searchMusic({ q, limit: 10 });
        setSearchResults(res.items);
      } else {
        const res = await albumApi.searchAlbums({ q, limit: 10 });
        setSearchResults(res.items);
      }
    } catch {
      toast.error("搜索失败");
    }
  };

  const openCreate = () => {
    setEditingItem(null);
    setFormType("music");
    setFormTitle("");
    setFormDesc("");
    setSearchQ("");
    setSearchResults([]);
    setSelectedTarget(null);
    setModalOpen(true);
  };

  const openEdit = (item: CarouselItem) => {
    setEditingItem(item);
    setFormType(item.type);
    setFormTitle(item.title);
    setFormDesc(item.description);
    setSearchQ("");
    setSearchResults([]);
    setSelectedTarget({ id: item.target_id, title: item.title });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    if (!formTitle.trim()) { toast.error("请输入推送标题"); return; }
    if (!selectedTarget) { toast.error("请选择一个音乐或专辑"); return; }

    setSubmitting(true);
    try {
      const input: CarouselCreateInput = {
        type: formType,
        target_id: selectedTarget.id,
        title: formTitle.trim(),
        description: formDesc.trim(),
      };
      if (editingItem) {
        await carouselApi.updateCarouselItem(editingItem.id, {
          title: input.title,
          description: input.description,
        });
        toast.success("推图已更新");
      } else {
        await carouselApi.createCarouselItem(input);
        toast.success("推图已创建");
      }
      setModalOpen(false);
      loadItems();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await carouselApi.deleteCarouselItem(deleteTarget.id);
      toast.success("推图已删除");
      setDeleteTarget(null);
      loadItems();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const handleMoveUp = async (index: number) => {
    if (index <= 0) return;
    const newIds = items.map((it) => it.id);
    [newIds[index - 1], newIds[index]] = [newIds[index], newIds[index - 1]];
    try {
      await carouselApi.reorderCarouselItems(newIds);
      loadItems();
    } catch {
      toast.error("排序失败");
    }
  };

  const handleMoveDown = async (index: number) => {
    if (index >= items.length - 1) return;
    const newIds = items.map((it) => it.id);
    [newIds[index], newIds[index + 1]] = [newIds[index + 1], newIds[index]];
    try {
      await carouselApi.reorderCarouselItems(newIds);
      loadItems();
    } catch {
      toast.error("排序失败");
    }
  };

  return (
    <div>
      <FadeIn>
        <div className="admin-page-header">
          <PageTitle icon={Image} iconAccent="pink">推图管理</PageTitle>
          <motion.button
            className="btn-primary"
            onClick={openCreate}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
          >
            <Plus size={16} /> 新增推图
          </motion.button>
        </div>
      </FadeIn>

      {loading ? (
        <div className="empty-state"><p>加载中...</p></div>
      ) : items.length === 0 ? (
        <EmptyState icon={Image} title="暂无推图" description="点击「新增推图」添加首页轮播内容。" accent="pink" />
      ) : (
        <div className="admin-table-container">
          <div className="admin-table-header" style={{ gridTemplateColumns: "40px 1fr 100px 120px 100px" }}>
            <span>#</span>
            <span>标题</span>
            <span>类型</span>
            <span>目标 ID</span>
            <span>操作</span>
          </div>
          {items.map((item, i) => (
            <div
              key={item.id}
              className="admin-table-row"
              style={{ gridTemplateColumns: "40px 1fr 100px 120px 100px" }}
            >
              <span style={{ fontSize: 13, color: "var(--color-muted)" }}>{i + 1}</span>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{item.title}</div>
                <div style={{ fontSize: 12, color: "var(--color-muted)", marginTop: 2 }}>
                  {item.description || "—"}
                </div>
              </div>
              <span className="badge-pill" style={{ width: "fit-content", fontSize: 12 }}>
                {item.type === "music" ? "音乐" : "专辑"}
              </span>
              <span style={{ fontSize: 13, color: "var(--color-muted)" }}>{item.target_id}</span>
              <div style={{ display: "flex", gap: 4 }}>
                <button type="button" className="admin-table-action-btn" onClick={() => handleMoveUp(i)} title="上移">
                  <GripVertical size={14} style={{ transform: "rotate(-90deg)" }} />
                </button>
                <button type="button" className="admin-table-action-btn" onClick={() => handleMoveDown(i)} title="下移">
                  <GripVertical size={14} style={{ transform: "rotate(90deg)" }} />
                </button>
                <button type="button" className="admin-table-action-btn" onClick={() => openEdit(item)} title="编辑">
                  <Pencil size={14} />
                </button>
                <button
                  type="button"
                  className="admin-table-action-btn"
                  onClick={() => setDeleteTarget(item)}
                  title="删除"
                  style={{ color: "var(--color-error)" }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 创建/编辑弹窗 */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingItem ? "编辑推图" : "新增推图"}
        maxWidth={480}
        footer={
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <motion.button className="ghost-button" onClick={() => setModalOpen(false)} disabled={submitting} whileTap={{ scale: 0.97 }} type="button">
              取消
            </motion.button>
            <motion.button className="btn-primary" onClick={() => void handleSubmit()} disabled={submitting} whileTap={{ scale: 0.97 }} type="button">
              {submitting ? "保存中..." : "确定"}
            </motion.button>
          </div>
        }
      >
        <div className="form-stack">
          {/* 类型选择 */}
          <div className="form-field">
            <span className="form-field-label">推送种类</span>
            <select
              value={formType}
              onChange={(e) => {
                setFormType(e.target.value as "music" | "album");
                setSelectedTarget(null);
                setSearchResults([]);
                setSearchQ("");
              }}
              disabled={!!editingItem}
            >
              <option value="music">音乐</option>
              <option value="album">专辑</option>
            </select>
          </div>

          {/* 搜索目标 */}
          <div className="form-field">
            <span className="form-field-label">
              {formType === "music" ? "搜索音乐" : "搜索专辑"}
            </span>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder={formType === "music" ? "输入音乐名称..." : "输入专辑名称..."}
                onKeyDown={(e) => e.key === "Enter" && void handleSearch()}
                disabled={!!editingItem}
                style={{ flex: 1 }}
              />
              <motion.button
                type="button"
                className="btn-primary"
                onClick={() => void handleSearch()}
                disabled={!!editingItem}
                whileTap={{ scale: 0.95 }}
                style={{ padding: "0 12px", minHeight: 44, flexShrink: 0 }}
              >
                <Search size={16} />
              </motion.button>
            </div>
          </div>

          {/* 搜索结果 */}
          {searchResults.length > 0 && (
            <div style={{ maxHeight: 160, overflowY: "auto", border: "1px solid var(--color-hairline)", borderRadius: 8 }}>
              {searchResults.map((r) => (
                <div
                  key={r.id}
                  onClick={() => {
                    setSelectedTarget({ id: r.id, title: r.title });
                    if (!editingItem) setFormTitle(r.title);
                    setSearchResults([]);
                  }}
                  style={{
                    padding: "8px 12px",
                    cursor: "pointer",
                    fontSize: 13,
                    borderBottom: "1px solid var(--color-hairline-soft)",
                    background: selectedTarget?.id === r.id ? "var(--color-surface-soft)" : "transparent",
                  }}
                >
                  {r.title}
                </div>
              ))}
            </div>
          )}

          {/* 已选择的目标 */}
          {selectedTarget && (
            <div style={{ fontSize: 13, color: "var(--color-brand-teal)", fontWeight: 500 }}>
              已选择：{selectedTarget.title} (ID: {selectedTarget.id})
            </div>
          )}

          {/* 标题 */}
          <div className="form-field">
            <span className="form-field-label">
              推送标题 <span style={{ color: "var(--color-error)" }}>*</span>
            </span>
            <input
              value={formTitle}
              onChange={(e) => setFormTitle(e.target.value)}
              placeholder="显示在推图上的标题"
              maxLength={128}
            />
          </div>

          {/* 描述 */}
          <div className="form-field form-field--long">
            <span className="form-field-label">推送描述</span>
            <textarea
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="显示在推图上的描述文字"
              maxLength={256}
              rows={2}
            />
          </div>
        </div>
      </Modal>

      {/* 删除确认弹窗 */}
      <ConfirmDeleteModal
        open={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDelete()}
        itemType="推图"
        itemName={deleteTarget?.title ?? ""}
        loading={deleting}
      />
    </div>
  );
};
