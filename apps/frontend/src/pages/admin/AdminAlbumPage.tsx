import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Plus,
  Pencil,
  Trash2,
  ListMusic,
  Disc3,
  Music,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { albumApi, musicApi } from "../../shared/api/instances";
import { useAuthStore } from "../../shared/stores/authStore";
import type { AdminAlbumListItem, AlbumDetail, MusicListItem } from "../../shared/api/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";
import {
  ImagePreviewZone,
  AuthorSelect,
  type AuthorInfo,
} from "./_musicFormComponents";

/* ======================================================================== */
/** 专辑管理页面。
 *
 * 提供专辑的完整 CRUD 及歌曲管理功能：
 * - 列表展示（含封面、标题、作者、歌曲数、播放量等）
 * - 标题搜索 + 分页
 * - 新建专辑（弹窗，双栏布局）
 * - 编辑专辑（弹窗，支持文本修改和封面替换）
 * - 删除专辑（确认弹窗，软删除）
 * - 歌曲管理（弹窗，展示歌曲列表、添加/移除歌曲）
 */
export const AdminAlbumPage = () => {
  const { api } = useAuthStore();

  /* ---------- 列表状态 ---------- */
  const [albums, setAlbums] = useState<AdminAlbumListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  /* ---------- 弹窗状态 ---------- */
  const [createOpen, setCreateOpen] = useState(false);
  const [editAlbum, setEditAlbum] = useState<AlbumDetail | null>(null);
  const [deleteAlbum, setDeleteAlbum] = useState<AdminAlbumListItem | null>(null);
  const [manageAlbum, setManageAlbum] = useState<AlbumDetail | null>(null);

  /* ---------- 表单状态（新建/编辑共用） ---------- */
  const [formTitle, setFormTitle] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formSource, setFormSource] = useState("");
  const [formCoverIcon, setFormCoverIcon] = useState<File | null>(null);
  const [formCover, setFormCover] = useState<File | null>(null);
  const [formAuthors, setFormAuthors] = useState<AuthorInfo[]>([]);
  const [submitting, setSubmitting] = useState(false);

  /* ---------- 歌曲管理状态 ---------- */
  const [musicSearchQuery, setMusicSearchQuery] = useState("");
  const [musicSearchResults, setMusicSearchResults] = useState<MusicListItem[]>([]);
  const [musicSearchLoading, setMusicSearchLoading] = useState(false);

  const loadAlbums = useCallback(async () => {
    setLoading(true);
    try {
      const result = await albumApi.adminListAlbums({
        q: query || undefined,
        limit: pageSize,
        offset: page * pageSize,
      });
      setAlbums(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [query, page, pageSize]);

  useEffect(() => {
    loadAlbums();
  }, [loadAlbums]);

  const handleSearch = () => setPage(0);
  const totalPages = Math.ceil(total / pageSize);

  /* ---------- 重置表单 ---------- */
  const resetForm = () => {
    setFormTitle("");
    setFormDescription("");
    setFormSource("");
    setFormCoverIcon(null);
    setFormCover(null);
    setFormAuthors([]);
  };

  /* ---------- 新建 ---------- */
  const handleCreate = async () => {
    if (!formTitle.trim() || !formCoverIcon || !formCover) {
      toast.error("请填写标题并上传两张封面图片");
      return;
    }
    setSubmitting(true);
    try {
      await albumApi.adminCreateAlbum({
        title: formTitle.trim(),
        description: formDescription || undefined,
        source: formSource || undefined,
        cover_icon: formCoverIcon,
        cover: formCover,
        author_ids: formAuthors.length > 0 ? formAuthors.map((a) => a.id) : undefined,
      });
      toast.success("专辑创建成功");
      setCreateOpen(false);
      resetForm();
      loadAlbums();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  };

  /* ---------- 编辑 ---------- */
  const openEdit = async (album: AdminAlbumListItem) => {
    try {
      const detail = await albumApi.getAlbumDetail(album.id);
      setEditAlbum(detail);
      setFormTitle(detail.title);
      setFormDescription(detail.description ?? "");
      setFormSource(detail.source ?? "");
      setFormCoverIcon(null);
      setFormCover(null);
      setFormAuthors(
        detail.authors.map((a) => ({
          id: a.id,
          nickname: a.nickname,
          username: a.username,
        })),
      );
    } catch {
      toast.error("加载专辑详情失败");
    }
  };

  const handleEdit = async () => {
    if (!editAlbum) return;
    if (!formTitle.trim()) {
      toast.error("标题不能为空");
      return;
    }
    setSubmitting(true);
    try {
      // 先更新文本信息
      await albumApi.adminUpdateAlbum(editAlbum.id, {
        title: formTitle.trim(),
        description: formDescription || undefined,
        source: formSource || undefined,
        author_ids: formAuthors.length > 0 ? formAuthors.map((a) => a.id) : undefined,
      });

      // 如有新封面，再更新封面
      if (formCoverIcon || formCover) {
        await albumApi.adminUpdateAlbumCovers(editAlbum.id, {
          cover_icon: formCoverIcon ?? undefined,
          cover: formCover ?? undefined,
        });
      }

      toast.success("专辑信息已更新");
      setEditAlbum(null);
      resetForm();
      loadAlbums();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新失败");
    } finally {
      setSubmitting(false);
    }
  };

  /* ---------- 删除 ---------- */
  const [deleteConfirmInput, setDeleteConfirmInput] = useState("");
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const handleDelete = async () => {
    if (!deleteAlbum || deleteConfirmInput !== deleteAlbum.title) return;
    setDeleteSubmitting(true);
    try {
      await albumApi.adminDeleteAlbum(deleteAlbum.id);
      setAlbums((prev) => prev.filter((a) => a.id !== deleteAlbum.id));
      setTotal((t) => t - 1);
      toast.success("专辑已删除");
      setDeleteAlbum(null);
      setDeleteConfirmInput("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleteSubmitting(false);
    }
  };

  /* ---------- 歌曲管理 ---------- */
  const openManage = async (album: AdminAlbumListItem) => {
    try {
      const detail = await albumApi.getAlbumDetail(album.id);
      setManageAlbum(detail);
    } catch {
      toast.error("加载专辑详情失败");
    }
  };

  const handleRemoveMusic = async (musicId: number) => {
    if (!manageAlbum) return;
    try {
      await albumApi.adminRemoveMusicFromAlbum(manageAlbum.id, musicId);
      const detail = await albumApi.getAlbumDetail(manageAlbum.id);
      setManageAlbum(detail);
      toast.success("已移除歌曲");
      // 同步更新列表中的歌曲数
      setAlbums((prev) =>
        prev.map((a) =>
          a.id === manageAlbum.id ? { ...a, music_count: a.music_count - 1 } : a,
        ),
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "移除失败");
    }
  };

  const handleSearchMusic = async () => {
    if (!musicSearchQuery.trim()) {
      setMusicSearchResults([]);
      return;
    }
    setMusicSearchLoading(true);
    try {
      const result = await musicApi.searchMusic({
        q: musicSearchQuery.trim(),
        limit: 10,
        offset: 0,
      });
      setMusicSearchResults(result.items);
    } catch {
      toast.error("搜索音乐失败");
    } finally {
      setMusicSearchLoading(false);
    }
  };

  const handleAddMusic = async (musicId: number) => {
    if (!manageAlbum) return;
    try {
      await albumApi.adminAddMusicToAlbum(manageAlbum.id, musicId);
      const detail = await albumApi.getAlbumDetail(manageAlbum.id);
      setManageAlbum(detail);
      toast.success("歌曲已添加");
      // 同步更新列表中的歌曲数
      setAlbums((prev) =>
        prev.map((a) =>
          a.id === manageAlbum.id ? { ...a, music_count: a.music_count + 1 } : a,
        ),
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("409") || msg.includes("Conflict") || msg.includes("already")) {
        toast.error("该歌曲已在专辑中或属于其他专辑");
      } else {
        toast.error(msg || "添加失败");
      }
    }
  };

  /* ---------- 弹窗关闭清理 ---------- */
  const closeCreate = () => {
    setCreateOpen(false);
    resetForm();
  };

  const closeEdit = () => {
    setEditAlbum(null);
    resetForm();
  };

  const closeDelete = () => {
    setDeleteAlbum(null);
    setDeleteConfirmInput("");
  };

  const closeManage = () => {
    setManageAlbum(null);
    setMusicSearchQuery("");
    setMusicSearchResults([]);
  };

  /* ---------- 表单弹窗内容（新建/编辑共用） ---------- */
  const renderForm = (isEdit: boolean) => (
    <div className="import-form-grid">
      {/* 左栏：基本信息 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="import-section">
          <h3 className="import-section-title">基本信息</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <label>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-ink)",
                  display: "block",
                  marginBottom: 4,
                }}
              >
                标题 <span style={{ color: "var(--color-danger)" }}>*</span>
              </span>
              <input
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder="请输入专辑名称"
                style={{ fontSize: 14 }}
              />
            </label>
            <label>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-ink)",
                  display: "block",
                  marginBottom: 4,
                }}
              >
                描述
              </span>
              <textarea
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="专辑描述（可选）"
                rows={3}
                style={{ fontSize: 14 }}
              />
            </label>
            <label>
              <span
                style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: "var(--color-ink)",
                  display: "block",
                  marginBottom: 4,
                }}
              >
                来源
              </span>
              <input
                value={formSource}
                onChange={(e) => setFormSource(e.target.value)}
                placeholder="如：网易云音乐、原创"
                style={{ fontSize: 14 }}
              />
            </label>
          </div>
        </div>
      </div>

      {/* 右栏：封面 + 作者 */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="import-section">
          <h3 className="import-section-title">封面图片</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <ImagePreviewZone
              label="封面图标"
              required={!isEdit}
              file={formCoverIcon}
              existingUrl={isEdit ? editAlbum?.cover_icon_url : undefined}
              onChange={setFormCoverIcon}
              height={140}
            />
            <ImagePreviewZone
              label="封面大图"
              required={!isEdit}
              file={formCover}
              existingUrl={isEdit ? editAlbum?.cover_url : undefined}
              onChange={setFormCover}
              height={140}
            />
          </div>
        </div>

        <div className="import-section">
          <h3 className="import-section-title">作者</h3>
          <AuthorSelect
            selectedAuthors={formAuthors}
            onChange={setFormAuthors}
            searchUsers={async (q) => {
              try {
                return await api.searchUsers(q, 10, 0);
              } catch {
                return undefined;
              }
            }}
          />
        </div>
      </div>
    </div>
  );

  return (
    <>
      <PaginatedPageLayout
        header={(
          <>
      {/* ========== 页面标题 + 新建按钮 ========== */}
      <FadeIn>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 20,
          }}
        >
          <h1 className="page-title">专辑管理</h1>
          <motion.button
            className="btn-primary"
            onClick={() => setCreateOpen(true)}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
          >
            <Plus size={16} />
            新建专辑
          </motion.button>
        </div>
      </FadeIn>

      {/* ========== 搜索栏 ========== */}
      <FadeIn delay={0.08}>
        <div
          style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "center" }}
        >
          <div style={{ position: "relative", flex: 1, maxWidth: 400 }}>
            <Search
              size={14}
              style={{
                position: "absolute",
                left: 10,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--color-muted)",
              }}
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索专辑标题..."
              style={{ paddingLeft: 32 }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <motion.button
            className="primary-button"
            onClick={handleSearch}
            disabled={loading}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            {loading ? "加载中" : "搜索"}
          </motion.button>
        </div>
      </FadeIn>
          </>
        )}
        footer={
          albums.length > 0 && (totalPages > 1 || total > 0) ? (
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(0);
              }}
              loading={loading}
              total={total}
            />
          ) : undefined
        }
      >
      {/* ========== 表格 ========== */}
      {albums.length > 0 ? (
        <FadeIn delay={0.15}>
          <div className="admin-table-container" style={{ overflowX: "auto" }}>
            <div
              className="admin-table-header"
              style={{
                gridTemplateColumns: "50px 50px 1.5fr 1fr 80px 100px 100px 120px 120px",
                minWidth: 900,
              }}
            >
              <span>ID</span>
              <span>封面</span>
              <span>标题</span>
              <span>作者</span>
              <span>歌曲数</span>
              <span>播放量</span>
              <span>收藏数</span>
              <span>创建时间</span>
              <span>操作</span>
            </div>
            <StaggerContainer staggerDelay={0.03}>
              {albums.map((item) => (
                <StaggerItem key={item.id}>
                  <motion.div
                    className="admin-table-row"
                    style={{
                      gridTemplateColumns:
                        "50px 50px 1.5fr 1fr 80px 100px 100px 120px 120px",
                      alignItems: "center",
                      minWidth: 900,
                    }}
                    whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                  >
                    <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
                      {item.id}
                    </span>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {item.cover_icon_url ? (
                        <img
                          src={item.cover_icon_url}
                          alt={item.title}
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 4,
                            objectFit: "cover",
                            flexShrink: 0,
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 4,
                            background: "var(--color-border)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <Disc3 size={16} color="var(--color-muted)" />
                        </div>
                      )}
                    </div>
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.title}
                    </span>
                    <span
                      style={{
                        fontSize: 13,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {item.authors.map((a) => a.nickname).join(", ") || "—"}
                    </span>
                    <span style={{ fontSize: 13, textAlign: "center" }}>
                      {item.music_count}
                    </span>
                    <span style={{ fontSize: 13 }}>{item.play_count}</span>
                    <span style={{ fontSize: 13 }}>{item.collect_count ?? 0}</span>
                    <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
                      {item.created_at
                        ? new Date(item.created_at).toLocaleDateString("zh-CN")
                        : "—"}
                    </span>
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
                        onClick={() => openManage(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="管理歌曲"
                        style={{ padding: "6px 8px", minHeight: "auto" }}
                      >
                        <ListMusic size={14} />
                      </motion.button>
                      <motion.button
                        className="ghost-button"
                        onClick={() => {
                          setDeleteAlbum(item);
                          setDeleteConfirmInput("");
                        }}
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
      ) : (
        <FadeIn delay={0.15}>
          <EmptyState
            icon={Disc3}
            title="暂无专辑"
            description="未找到符合条件的专辑，请尝试其他搜索关键词或新建专辑。"
          />
        </FadeIn>
      )}
      </PaginatedPageLayout>

      {/* ========== 新建弹窗 ========== */}
      <Modal
        open={createOpen}
        onClose={closeCreate}
        title="新建专辑"
        maxWidth={720}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={closeCreate}
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
              {submitting ? "创建中..." : "确认创建"}
            </motion.button>
          </>
        }
      >
        {renderForm(false)}
      </Modal>

      {/* ========== 编辑弹窗 ========== */}
      <Modal
        open={!!editAlbum}
        onClose={closeEdit}
        title="编辑专辑"
        maxWidth={720}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={closeEdit}
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
              {submitting ? "保存中..." : "保存"}
            </motion.button>
          </>
        }
      >
        {renderForm(true)}
      </Modal>

      {/* ========== 删除确认弹窗 ========== */}
      <Modal
        open={!!deleteAlbum}
        onClose={closeDelete}
        title="删除专辑"
        maxWidth={460}
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={closeDelete}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="danger-button"
              onClick={handleDelete}
              disabled={deleteSubmitting || !deleteAlbum || deleteConfirmInput !== deleteAlbum.title}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {deleteSubmitting ? "删除中..." : "确认删除"}
            </motion.button>
          </>
        }
      >
        {deleteAlbum && (
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
              <Trash2 size={20} style={{ color: "var(--color-danger)", flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: "var(--color-danger)" }}>
                此操作不可撤销，专辑将被软删除（公众不可见），但数据仍保留在数据库中。
              </span>
            </div>
            <p style={{ margin: 0, fontSize: 13, color: "var(--color-muted)" }}>
              请输入专辑标题 <strong>「{deleteAlbum.title}」</strong> 以确认删除。
            </p>
            <label>
              标题确认
              <input
                value={deleteConfirmInput}
                onChange={(e) => setDeleteConfirmInput(e.target.value)}
                placeholder={`请输入 "${deleteAlbum.title}"`}
                autoFocus
              />
            </label>
          </div>
        )}
      </Modal>

      {/* ========== 歌曲管理弹窗 ========== */}
      <Modal
        open={!!manageAlbum}
        onClose={closeManage}
        title={manageAlbum ? `管理歌曲：${manageAlbum.title}` : "管理歌曲"}
        maxWidth={640}
        footer={
          <motion.button
            className="ghost-button"
            onClick={closeManage}
            whileTap={{ scale: 0.97 }}
            type="button"
          >
            关闭
          </motion.button>
        }
      >
        {manageAlbum && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* 当前歌曲列表 */}
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 12,
                }}
              >
                <h4 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
                  <ListMusic size={14} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />
                  歌曲列表 ({manageAlbum.musics.length} 首)
                </h4>
              </div>

              {manageAlbum.musics.length === 0 ? (
                <EmptyState icon={Music} title="暂无歌曲" description="使用下方搜索添加歌曲到专辑。" compact />
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {manageAlbum.musics.map((music, i) => (
                    <div
                      key={music.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 12,
                        padding: "8px 0",
                        borderBottom: "1px solid var(--color-border)",
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          color: "var(--color-muted)",
                          width: 24,
                          textAlign: "center",
                        }}
                      >
                        {i + 1}
                      </span>
                      {music.cover_icon_url ? (
                        <img
                          src={music.cover_icon_url}
                          alt={music.title}
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 4,
                            objectFit: "cover",
                            flexShrink: 0,
                          }}
                        />
                      ) : (
                        <div
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 4,
                            background: "var(--color-border)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            flexShrink: 0,
                          }}
                        >
                          <Music size={14} color="var(--color-muted)" />
                        </div>
                      )}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight: 500,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {music.title}
                          {music.is_vip && (
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 600,
                                color: "var(--color-accent-2)",
                                marginLeft: 6,
                              }}
                            >
                              VIP
                            </span>
                          )}
                        </div>
                      </div>
                      <motion.button
                        className="ghost-button"
                        onClick={() => handleRemoveMusic(music.id)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title="移除"
                        style={{
                          padding: "4px 8px",
                          minHeight: "auto",
                          color: "var(--color-danger)",
                        }}
                      >
                        <Trash2 size={14} />
                      </motion.button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 添加歌曲 */}
            <div
              style={{
                padding: 16,
                background: "var(--color-surface-soft)",
                borderRadius: 10,
                border: "1px solid var(--color-border)",
              }}
            >
              <h4 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600 }}>
                <Plus size={14} style={{ display: "inline", verticalAlign: "-2px", marginRight: 6 }} />
                添加歌曲
              </h4>
              <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                <input
                  value={musicSearchQuery}
                  onChange={(e) => setMusicSearchQuery(e.target.value)}
                  placeholder="搜索音乐标题..."
                  style={{ flex: 1, fontSize: 13 }}
                  onKeyDown={(e) => e.key === "Enter" && handleSearchMusic()}
                />
                <motion.button
                  className="primary-button"
                  onClick={handleSearchMusic}
                  disabled={musicSearchLoading}
                  whileTap={{ scale: 0.97 }}
                  type="button"
                  style={{ fontSize: 13, padding: "6px 14px" }}
                >
                  {musicSearchLoading ? "搜索中" : "搜索"}
                </motion.button>
              </div>

              {musicSearchResults.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 240, overflowY: "auto" }}>
                  {musicSearchResults.map((music) => {
                    const alreadyIn = manageAlbum.musics.some((m) => m.id === music.id);
                    return (
                      <div
                        key={music.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          padding: "8px 10px",
                          borderRadius: 8,
                          background: alreadyIn ? "rgba(0,0,0,0.02)" : "transparent",
                        }}
                      >
                        {music.cover_icon_url ? (
                          <img
                            src={music.cover_icon_url}
                            alt={music.title}
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 4,
                              objectFit: "cover",
                              flexShrink: 0,
                            }}
                          />
                        ) : (
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: 4,
                              background: "var(--color-border)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <Music size={14} color="var(--color-muted)" />
                          </div>
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              fontSize: 13,
                              fontWeight: 500,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {music.title}
                          </div>
                          <div style={{ fontSize: 11, color: "var(--color-muted)" }}>
                            {music.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
                          </div>
                        </div>
                        {alreadyIn ? (
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--color-muted)",
                              padding: "2px 8px",
                            }}
                          >
                            已在专辑中
                          </span>
                        ) : (
                          <motion.button
                            className="btn-primary"
                            onClick={() => handleAddMusic(music.id)}
                            whileHover={{ scale: 1.03 }}
                            whileTap={{ scale: 0.97 }}
                            type="button"
                            style={{
                              fontSize: 12,
                              padding: "4px 10px",
                              minHeight: "auto",
                            }}
                          >
                            添加
                          </motion.button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {musicSearchQuery.trim() && !musicSearchLoading && musicSearchResults.length === 0 && (
                <p style={{ fontSize: 13, color: "var(--color-muted)", margin: 0 }}>
                  未找到匹配的音乐
                </p>
              )}
            </div>
          </div>
        )}
      </Modal>
    </>
  );
};
