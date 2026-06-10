import { useEffect, useState, useCallback } from "react";
import {
  Search,
  Pencil,
  ArrowUpCircle,
  ArrowDownCircle,
  Music,
  Plus,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { createMusicApi } from "../../shared/api/musicApi";
import { createDictionaryApi } from "../../shared/api/dictionaryApi";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import { useAuthStore } from "../../shared/stores/authStore";
import type { MusicDetail, AdminMusicListItem, DictionaryItem } from "../../shared/api/types";
import { EmptyState } from "../../components/ui/EmptyState";
import { Modal } from "../../components/ui/Modal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { FadeIn } from "../../components/motion/FadeIn";
import { StaggerContainer, StaggerItem } from "../../components/motion/StaggerContainer";
import {
  CompactFileRow,
  ImagePreviewZone,
  SearchableTagSelect,
  AuthorSelect,
  type AuthorInfo,
} from "./_musicFormComponents";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });
const dictionaryApi = createDictionaryApi({ baseUrl: API_BASE_URL, tokenStore });

/**
 * 音乐管理页面。
 *
 * 使用管理员专用接口 /music/admin/list，可查询所有音乐（含未上架），
 * 支持按标题搜索、风格/语言/上架状态筛选及分页。
 * 编辑弹窗支持替换音频、歌词、封面图片，使用与导入页面一致的交互风格。
 */
export const AdminMusicPage = () => {
  const navigate = useNavigate();
  const { api } = useAuthStore();

  /* ---------- 列表状态 ---------- */
  const [musics, setMusics] = useState<AdminMusicListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [styleFilter, setStyleFilter] = useState<string>("");
  const [languageFilter, setLanguageFilter] = useState<string>("");
  const [publishedFilter, setPublishedFilter] = useState<string>("");
  const [vipFilter, setVipFilter] = useState<string>("");
  const [instrumentFilter, setInstrumentFilter] = useState<string>("");
  const [emotionTagFilter, setEmotionTagFilter] = useState<string>("");
  const [interestTagFilter, setInterestTagFilter] = useState<string>("");
  const [styles, setStyles] = useState<DictionaryItem[]>([]);
  const [languages, setLanguages] = useState<DictionaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  /* ---------- 编辑弹窗状态 ---------- */
  const [editMusic, setEditMusic] = useState<MusicDetail | null>(null);
  const [editForm, setEditForm] = useState<{
    title: string;
    source: string;
    style_id: number | "";
    language_id: number | "";
    release_date: string;
    is_vip: boolean;
  }>({
    title: "",
    source: "",
    style_id: "",
    language_id: "",
    release_date: "",
    is_vip: false,
  });
  const [editAudioFile, setEditAudioFile] = useState<File | null>(null);
  const [editLyricsFile, setEditLyricsFile] = useState<File | null>(null);
  const [editCoverIconFile, setEditCoverIconFile] = useState<File | null>(null);
  const [editCoverHomeFile, setEditCoverHomeFile] = useState<File | null>(null);
  const [editCoverPlayFile, setEditCoverPlayFile] = useState<File | null>(null);
  const [editInstrumentIds, setEditInstrumentIds] = useState<number[]>([]);
  const [editEmotionTagIds, setEditEmotionTagIds] = useState<number[]>([]);
  const [editInterestTagIds, setEditInterestTagIds] = useState<number[]>([]);
  const [editSelectedAuthors, setEditSelectedAuthors] = useState<AuthorInfo[]>([]);
  const [editSubmitting, setEditSubmitting] = useState(false);

  /* ---------- 字典数据（编辑弹窗需要） ---------- */
  const [instruments, setInstruments] = useState<DictionaryItem[]>([]);
  const [emotionTags, setEmotionTags] = useState<DictionaryItem[]>([]);
  const [interestTags, setInterestTags] = useState<DictionaryItem[]>([]);

  const loadMusics = useCallback(async () => {
    setLoading(true);
    try {
      const result = await musicApi.adminListMusic({
        q: query || undefined,
        style_id: styleFilter ? Number(styleFilter) : undefined,
        language_id: languageFilter ? Number(languageFilter) : undefined,
        is_published: publishedFilter === "" ? undefined : publishedFilter === "true",
        is_vip: vipFilter === "" ? undefined : vipFilter === "true",
        instrument_id: instrumentFilter ? Number(instrumentFilter) : undefined,
        emotion_tag_id: emotionTagFilter ? Number(emotionTagFilter) : undefined,
        interest_tag_id: interestTagFilter ? Number(interestTagFilter) : undefined,
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
  }, [
    query,
    styleFilter,
    languageFilter,
    publishedFilter,
    vipFilter,
    instrumentFilter,
    emotionTagFilter,
    interestTagFilter,
    page,
    pageSize,
  ]);

  useEffect(() => {
    loadMusics();
  }, [loadMusics]);

  useEffect(() => {
    const loadDict = async () => {
      try {
        const [s, l, i, e, it] = await Promise.all([
          dictionaryApi.listDictionary("styles"),
          dictionaryApi.listDictionary("languages"),
          dictionaryApi.listDictionary("instruments"),
          dictionaryApi.listDictionary("emotion_tags"),
          dictionaryApi.listDictionary("interest_tags"),
        ]);
        setStyles(s.items);
        setLanguages(l.items);
        setInstruments(i.items);
        setEmotionTags(e.items);
        setInterestTags(it.items);
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

  /* ---------- 打开编辑弹窗 ---------- */
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
      setEditAudioFile(null);
      setEditLyricsFile(null);
      setEditCoverIconFile(null);
      setEditCoverHomeFile(null);
      setEditCoverPlayFile(null);
      setEditInstrumentIds(detail.instruments.map((i) => i.id));
      setEditEmotionTagIds(detail.emotion_tags.map((t) => t.id));
      setEditInterestTagIds(detail.interest_tags.map((t) => t.id));
      setEditSelectedAuthors(
        detail.authors.map((a) => ({
          id: a.id,
          nickname: a.nickname,
          username: a.username,
        }))
      );
    } catch {
      toast.error("加载歌曲详情失败");
    }
  };

  const closeEdit = () => {
    setEditMusic(null);
    setEditAudioFile(null);
    setEditLyricsFile(null);
    setEditCoverIconFile(null);
    setEditCoverHomeFile(null);
    setEditCoverPlayFile(null);
  };

  /* ---------- 提交编辑 ---------- */
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
        instrument_ids: editInstrumentIds.length > 0 ? editInstrumentIds : undefined,
        emotion_tag_ids: editEmotionTagIds.length > 0 ? editEmotionTagIds : undefined,
        interest_tag_ids: editInterestTagIds.length > 0 ? editInterestTagIds : undefined,
        author_ids: editSelectedAuthors.length > 0 ? editSelectedAuthors.map((a) => a.id) : undefined,
        audio_file: editAudioFile ?? undefined,
        cover_icon: editCoverIconFile ?? undefined,
        cover_home: editCoverHomeFile ?? undefined,
        cover_play: editCoverPlayFile ?? undefined,
        lyrics_file: editLyricsFile ?? undefined,
      });
      toast.success("歌曲信息已更新");
      closeEdit();
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

          <select
            value={vipFilter}
            onChange={(e) => { setVipFilter(e.target.value); setPage(0); }}
            style={{ width: 100, fontSize: 13 }}
          >
            <option value="">全部 VIP</option>
            <option value="true">VIP</option>
            <option value="false">普通</option>
          </select>

          <div style={{ width: 140 }}>
            <SearchableTagSelect
              label="乐器"
              items={instruments}
              selectedIds={instrumentFilter ? [Number(instrumentFilter)] : []}
              onToggle={(id) => {
                setInstrumentFilter((prev) => (prev === String(id) ? "" : String(id)));
                setPage(0);
              }}
              mode="single"
              placeholder="搜索乐器..."
              showLabel={false}
            />
          </div>

          <div style={{ width: 140 }}>
            <SearchableTagSelect
              label="情感"
              items={emotionTags}
              selectedIds={emotionTagFilter ? [Number(emotionTagFilter)] : []}
              onToggle={(id) => {
                setEmotionTagFilter((prev) => (prev === String(id) ? "" : String(id)));
                setPage(0);
              }}
              mode="single"
              placeholder="搜索情感..."
              showLabel={false}
            />
          </div>

          <div style={{ width: 140 }}>
            <SearchableTagSelect
              label="兴趣"
              items={interestTags}
              selectedIds={interestTagFilter ? [Number(interestTagFilter)] : []}
              onToggle={(id) => {
                setInterestTagFilter((prev) => (prev === String(id) ? "" : String(id)));
                setPage(0);
              }}
              mode="single"
              placeholder="搜索兴趣..."
              showLabel={false}
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
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "3px 10px",
                          borderRadius: 20,
                          fontSize: 12,
                          fontWeight: 600,
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
            <PaginationBar
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
              pageSize={pageSize}
              onPageSizeChange={(size) => { setPageSize(size); setPage(0); }}
              loading={loading}
              total={total}
            />
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

      {/* ========== 编辑弹窗 ========== */}
      <Modal
        open={!!editMusic}
        onClose={closeEdit}
        title="编辑歌曲信息"
        maxWidth={760}
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
          <div className="import-form-grid"
          >
            {/* 左栏 */}
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* 基本信息 */}
              <div className="import-section">
                <h3 className="import-section-title">基本信息</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <label>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 4 }}>
                      歌名
                    </span>
                    <input
                      value={editForm.title}
                      onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                      style={{ fontSize: 14 }}
                    />
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <label>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 4 }}>
                        来源
                      </span>
                      <input
                        value={editForm.source}
                        onChange={(e) => setEditForm((f) => ({ ...f, source: e.target.value }))}
                        style={{ fontSize: 14 }}
                      />
                    </label>
                    <label>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 4 }}>
                        发行日期
                      </span>
                      <input
                        type="date"
                        value={editForm.release_date}
                        onChange={(e) => setEditForm((f) => ({ ...f, release_date: e.target.value }))}
                        style={{ fontSize: 14 }}
                      />
                    </label>
                  </div>
                </div>
              </div>

              {/* 媒体文件 */}
              <div className="import-section">
                <h3 className="import-section-title">媒体文件</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <CompactFileRow
                    label="音频文件"
                    icon={Music}
                    file={editAudioFile}
                    existingUrl={editMusic.file_url}
                    onChange={setEditAudioFile}
                    accept="audio/mpeg,audio/mp3,audio/flac,audio/wav,audio/ogg,audio/aac"
                  />
                  <CompactFileRow
                    label="歌词文件"
                    icon={FileText}
                    file={editLyricsFile}
                    existingUrl={editMusic.lyrics_url}
                    onChange={setEditLyricsFile}
                    accept=".lrc,.txt"
                  />
                </div>
              </div>

              {/* 封面图片 */}
              <div className="import-section">
                <h3 className="import-section-title">封面图片</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <ImagePreviewZone
                    label="封面图标"
                    file={editCoverIconFile}
                    existingUrl={editMusic.cover_icon_url}
                    onChange={setEditCoverIconFile}
                    height={160}
                  />
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <ImagePreviewZone
                      label="封面 Home"
                      file={editCoverHomeFile}
                      existingUrl={editMusic.cover_home_url}
                      onChange={setEditCoverHomeFile}
                      height={100}
                    />
                    <ImagePreviewZone
                      label="封面 Play"
                      file={editCoverPlayFile}
                      existingUrl={editMusic.cover_play_url}
                      onChange={setEditCoverPlayFile}
                      height={100}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* 右栏 */}
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              {/* 分类 */}
              <div className="import-section">
                <h3 className="import-section-title">分类</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <SearchableTagSelect
                    label="风格"
                    items={styles}
                    selectedIds={editForm.style_id !== "" ? [editForm.style_id as number] : []}
                    onToggle={(id) =>
                      setEditForm((f) => ({ ...f, style_id: f.style_id === id ? "" : id }))
                    }
                    mode="single"
                    placeholder="搜索风格..."
                  />
                  <SearchableTagSelect
                    label="语言"
                    items={languages}
                    selectedIds={editForm.language_id !== "" ? [editForm.language_id as number] : []}
                    onToggle={(id) =>
                      setEditForm((f) => ({ ...f, language_id: f.language_id === id ? "" : id }))
                    }
                    mode="single"
                    placeholder="搜索语言..."
                  />
                  <label className="import-toggle">
                    <input
                      type="checkbox"
                      checked={editForm.is_vip}
                      onChange={(e) => setEditForm((f) => ({ ...f, is_vip: e.target.checked }))}
                    />
                    <span className="import-toggle-switch" />
                    <span>VIP 专属</span>
                  </label>
                </div>
              </div>

              {/* 标签 */}
              <div className="import-section">
                <h3 className="import-section-title">标签</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <SearchableTagSelect
                    label="乐器"
                    items={instruments}
                    selectedIds={editInstrumentIds}
                    onToggle={(id) =>
                      setEditInstrumentIds((prev) =>
                        prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                      )
                    }
                    mode="multi"
                    placeholder="搜索乐器..."
                  />
                  <SearchableTagSelect
                    label="情感标签"
                    items={emotionTags}
                    selectedIds={editEmotionTagIds}
                    onToggle={(id) =>
                      setEditEmotionTagIds((prev) =>
                        prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                      )
                    }
                    mode="multi"
                    placeholder="搜索情感标签..."
                  />
                  <SearchableTagSelect
                    label="兴趣标签"
                    items={interestTags}
                    selectedIds={editInterestTagIds}
                    onToggle={(id) =>
                      setEditInterestTagIds((prev) =>
                        prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                      )
                    }
                    mode="multi"
                    placeholder="搜索兴趣标签..."
                  />
                </div>
              </div>

              {/* 作者 */}
              <div className="import-section">
                <h3 className="import-section-title">作者</h3>
                <AuthorSelect
                  selectedAuthors={editSelectedAuthors}
                  onChange={setEditSelectedAuthors}
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
        )}
      </Modal>
    </div>
  );
};
