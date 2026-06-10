import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Pencil,
  Eye,
  ArrowUpCircle,
  ArrowDownCircle,
  Music,
  Plus,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { createMusicApi } from "../../shared/api/musicApi";
import { createDictionaryApi } from "../../shared/api/dictionaryApi";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import type { MusicDetail, AdminMusicListItem, DictionaryItem } from "../../shared/api/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });
const dictionaryApi = createDictionaryApi({ baseUrl: API_BASE_URL, tokenStore });

/**
 * 音乐管理页面。
 *
 * 使用管理员专用接口 /music/admin/list，可查询所有音乐（含未上架），
 * 支持按标题搜索、风格/语言/上架状态筛选及分页。
 */
export const AdminMusicPage = () => {
  const navigate = useNavigate();
  const [musics, setMusics] = useState<AdminMusicListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [styleFilter, setStyleFilter] = useState<string>("");
  const [languageFilter, setLanguageFilter] = useState<string>("");
  const [publishedFilter, setPublishedFilter] = useState<string>("");
  const [styles, setStyles] = useState<DictionaryItem[]>([]);
  const [languages, setLanguages] = useState<DictionaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  // Modal states
  const [editMusic, setEditMusic] = useState<MusicDetail | null>(null);
  const [editForm, setEditForm] = useState<{
    title: string;
    source: string;
    style_id: number | "";
    language_id: number | "";
    release_date: string;
    is_vip: boolean;
  }>({ title: "", source: "", style_id: "", language_id: "", release_date: "", is_vip: false });
  const [editSubmitting, setEditSubmitting] = useState(false);

  const loadMusics = useCallback(async () => {
    setLoading(true);
    try {
      const result = await musicApi.adminListMusic({
        q: query || undefined,
        style_id: styleFilter ? Number(styleFilter) : undefined,
        language_id: languageFilter ? Number(languageFilter) : undefined,
        is_published: publishedFilter === "" ? undefined : publishedFilter === "true",
        limit: pageSize,
        offset: page * pageSize,
      });
      setMusics(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [query, styleFilter, languageFilter, publishedFilter, page, pageSize]);

  useEffect(() => {
    loadMusics();
  }, [loadMusics]);

  useEffect(() => {
    const loadDict = async () => {
      try {
        const [s, l] = await Promise.all([
          dictionaryApi.listDictionary("styles"),
          dictionaryApi.listDictionary("languages"),
        ]);
        setStyles(s.items);
        setLanguages(l.items);
      } catch {
        // silently fail
      }
    };
    loadDict();
  }, []);

  const handleSearch = () => setPage(0);

  const totalPages = Math.ceil(total / pageSize);

  const handleTogglePublish = async (music: AdminMusicListItem) => {
    try {
      if (music.is_published) {
        await musicApi.adminUnpublishMusic(music.id);
        toast.success("已下架");
      } else {
        await musicApi.adminPublishMusic(music.id);
        toast.success("已上架");
      }
      loadMusics();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "操作失败");
    }
  };

  const openEdit = async (music: AdminMusicListItem) => {
    try {
      const detail = await musicApi.adminGetMusicDetail(music.id);
      setEditMusic(detail);
      setEditForm({
        title: detail.title,
        source: detail.source ?? "",
        style_id: detail.style?.id ?? "",
        language_id: detail.language?.id ?? "",
        release_date: detail.release_date ?? "",
        is_vip: detail.is_vip,
      });
    } catch {
      toast.error("加载歌曲详情失败");
    }
  };

  const handleEditSubmit = async () => {
    if (!editMusic) return;
    setEditSubmitting(true);
    try {
      await musicApi.adminUpdateMusic(editMusic.id, {
        title: editForm.title,
        source: editForm.source || undefined,
        style_id: editForm.style_id ? Number(editForm.style_id) : undefined,
        language_id: editForm.language_id ? Number(editForm.language_id) : undefined,
        release_date: editForm.release_date || null,
        is_vip: editForm.is_vip,
      });
      toast.success("歌曲信息已更新");
      setEditMusic(null);
      loadMusics();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新失败");
    } finally {
      setEditSubmitting(false);
    }
  };

  return (
    <div>
      <FadeIn>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h1 className="page-title">音乐管理</h1>
          <motion.button
            className="btn-primary"
            onClick={() => navigate("/admin/music/import")}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
          >
            <Plus size={16} />
            导入音乐
          </motion.button>
        </div>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ position: "relative", flex: 1, maxWidth: 280 }}>
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
              placeholder="搜索歌名..."
              style={{ paddingLeft: 32 }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>

          <select
            value={styleFilter}
            onChange={(e) => { setStyleFilter(e.target.value); setPage(0); }}
            style={{ width: 130, fontSize: 13 }}
          >
            <option value="">全部风格</option>
            {styles.map((s) => (
              <option key={s.id} value={String(s.id)}>{s.name}</option>
            ))}
          </select>

          <select
            value={languageFilter}
            onChange={(e) => { setLanguageFilter(e.target.value); setPage(0); }}
            style={{ width: 130, fontSize: 13 }}
          >
            <option value="">全部语言</option>
            {languages.map((l) => (
              <option key={l.id} value={String(l.id)}>{l.name}</option>
            ))}
          </select>

          <select
            value={publishedFilter}
            onChange={(e) => { setPublishedFilter(e.target.value); setPage(0); }}
            style={{ width: 110, fontSize: 13 }}
          >
            <option value="">全部状态</option>
            <option value="true">已上架</option>
            <option value="false">未上架</option>
          </select>

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

      {musics.length > 0 ? (
        <FadeIn delay={0.15}>
          <div className="admin-table-container">
            <div
              className="admin-table-header"
              style={{ gridTemplateColumns: "50px 1.5fr 0.8fr 0.8fr 0.6fr 0.7fr 100px" }}
            >
              <span>ID</span>
              <span>歌曲</span>
              <span>风格</span>
              <span>语言</span>
              <span>播放量</span>
              <span>状态</span>
              <span>操作</span>
            </div>
            <StaggerContainer staggerDelay={0.03}>
              {musics.map((item) => (
                <StaggerItem key={item.id}>
                  <motion.div
                    className="admin-table-row"
                    style={{ gridTemplateColumns: "50px 1.5fr 0.8fr 0.8fr 0.6fr 0.7fr 100px", alignItems: "center" }}
                    whileHover={{ backgroundColor: "var(--color-surface-soft)" }}
                  >
                    <span style={{ fontSize: 12, color: "var(--color-muted)" }}>{item.id}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                      {item.cover_icon_url ? (
                        <img
                          src={item.cover_icon_url}
                          alt={item.title}
                          style={{ width: 36, height: 36, borderRadius: 4, objectFit: "cover", flexShrink: 0 }}
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
                          <Music size={16} color="var(--color-muted)" />
                        </div>
                      )}
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {item.title}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--color-muted)" }}>
                          {item.authors.map((a) => a.nickname).join(", ") || "未知艺人"}
                        </div>
                      </div>
                    </div>
                    <span style={{ fontSize: 13 }}>{item.style?.name ?? "—"}</span>
                    <span style={{ fontSize: 13 }}>{item.language?.name ?? "—"}</span>
                    <span style={{ fontSize: 13 }}>{item.play_count}</span>
                    <span>
                      <span
                        className={`status-badge ${item.is_published ? "active" : "banned"}`}
                        style={{
                          background: item.is_published ? "#e6f7f4" : "#f0eeea",
                          color: item.is_published ? "#2bb3a3" : "#77716a",
                        }}
                      >
                        {item.is_published ? "已上架" : "未上架"}
                      </span>
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
                        onClick={() => handleTogglePublish(item)}
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        type="button"
                        title={item.is_published ? "下架" : "上架"}
                        style={{ padding: "6px 8px", minHeight: "auto" }}
                      >
                        {item.is_published ? <ArrowDownCircle size={14} /> : <ArrowUpCircle size={14} />}
                      </motion.button>
                    </div>
                  </motion.div>
                </StaggerItem>
              ))}
            </StaggerContainer>
          </div>

          {totalPages > 1 && (
            <div className="pagination-bar">
              <div className="pagination-left">
                <span className="pagination-label">每页</span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(0); }}
                  className="pagination-size-select"
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
                <span className="pagination-label">条</span>
              </div>
              <div className="pagination-center">
                <motion.button
                  className="pagination-btn"
                  onClick={() => setPage(page - 1)}
                  disabled={page === 0 || loading}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                >
                  ←
                </motion.button>
                {Array.from({ length: totalPages }, (_, i) => i).map((p) => (
                  <motion.button
                    key={p}
                    className={`pagination-btn ${p === page ? "active" : ""}`}
                    onClick={() => setPage(p)}
                    disabled={loading}
                    whileTap={{ scale: 0.95 }}
                    type="button"
                  >
                    {p + 1}
                  </motion.button>
                ))}
                <motion.button
                  className="pagination-btn"
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages - 1 || loading}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                >
                  →
                </motion.button>
              </div>
              <span className="pagination-info">
                第 {page + 1} / {totalPages} 页，共 {total} 条
              </span>
            </div>
          )}
        </FadeIn>
      ) : (
        <FadeIn delay={0.15}>
          <EmptyState
            icon={Music}
            title="暂无音乐"
            description="未找到符合条件的音乐，请调整筛选条件或导入新音乐。"
          />
        </FadeIn>
      )}

      {/* Edit Modal */}
      <Modal
        open={!!editMusic}
        onClose={() => setEditMusic(null)}
        title="编辑歌曲信息"
        footer={
          <>
            <motion.button
              className="ghost-button"
              onClick={() => setEditMusic(null)}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              取消
            </motion.button>
            <motion.button
              className="primary-button"
              onClick={handleEditSubmit}
              disabled={editSubmitting}
              whileTap={{ scale: 0.97 }}
              type="button"
            >
              {editSubmitting ? "保存中..." : "保存"}
            </motion.button>
          </>
        }
      >
        {editMusic && (
          <div className="form-stack">
            <label>
              歌名
              <input
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                required
              />
            </label>
            <label>
              来源
              <input
                value={editForm.source}
                onChange={(e) => setEditForm((f) => ({ ...f, source: e.target.value }))}
              />
            </label>
            <label>
              风格
              <select
                value={String(editForm.style_id)}
                onChange={(e) => setEditForm((f) => ({ ...f, style_id: e.target.value ? Number(e.target.value) : "" }))}
              >
                <option value="">无</option>
                {styles.map((s) => (
                  <option key={s.id} value={String(s.id)}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              语言
              <select
                value={String(editForm.language_id)}
                onChange={(e) => setEditForm((f) => ({ ...f, language_id: e.target.value ? Number(e.target.value) : "" }))}
              >
                <option value="">无</option>
                {languages.map((l) => (
                  <option key={l.id} value={String(l.id)}>{l.name}</option>
                ))}
              </select>
            </label>
            <label>
              发行日期
              <input
                type="date"
                value={editForm.release_date}
                onChange={(e) => setEditForm((f) => ({ ...f, release_date: e.target.value }))}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={editForm.is_vip}
                onChange={(e) => setEditForm((f) => ({ ...f, is_vip: e.target.checked }))}
              />
              <span>VIP 专属</span>
            </label>
          </div>
        )}
      </Modal>
    </div>
  );
};
