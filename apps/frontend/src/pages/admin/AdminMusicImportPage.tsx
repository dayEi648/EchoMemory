import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  ArrowLeft,
  Music,
  FileText,
  ImageIcon,
  X,
  Search,
  User,
  Check,
} from "lucide-react";

import { createMusicApi } from "../../shared/api/musicApi";
import { createDictionaryApi } from "../../shared/api/dictionaryApi";
import { useAuthStore } from "../../shared/stores/authStore";
import { createLocalStorageTokenStore } from "../../shared/auth/tokenStore";
import type { DictionaryItem } from "../../shared/api/types";
import { FadeIn } from "../../components/motion/FadeIn";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";
const tokenStore = createLocalStorageTokenStore();
const musicApi = createMusicApi({ baseUrl: API_BASE_URL, tokenStore });
const dictionaryApi = createDictionaryApi({ baseUrl: API_BASE_URL, tokenStore });

interface AuthorInfo {
  id: number;
  nickname: string;
  username: string;
}

/* ========================================================================
   辅助 Hook：管理文件预览 URL 的创建与释放
   ======================================================================== */
const useFilePreview = (file: File | null) => {
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  return preview;
};

/* ========================================================================
   导入音乐页面
   ======================================================================== */
export const AdminMusicImportPage = () => {
  const navigate = useNavigate();
  const { api } = useAuthStore();

  /* ---------- 基本表单状态 ---------- */
  const [title, setTitle] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [coverIcon, setCoverIcon] = useState<File | null>(null);
  const [coverHome, setCoverHome] = useState<File | null>(null);
  const [coverPlay, setCoverPlay] = useState<File | null>(null);
  const [lyricsFile, setLyricsFile] = useState<File | null>(null);
  const [isVip, setIsVip] = useState(false);
  const [source, setSource] = useState("");
  const [releaseDate, setReleaseDate] = useState("");

  /* ---------- 分类：风格 & 语言（单选搜索） ---------- */
  const [styleId, setStyleId] = useState<number | null>(null);
  const [languageId, setLanguageId] = useState<number | null>(null);

  /* ---------- 标签：乐器 & 情感 & 兴趣（多选搜索） ---------- */
  const [instrumentIds, setInstrumentIds] = useState<number[]>([]);
  const [emotionTagIds, setEmotionTagIds] = useState<number[]>([]);
  const [interestTagIds, setInterestTagIds] = useState<number[]>([]);

  /* ---------- 作者（搜索多选） ---------- */
  const [selectedAuthors, setSelectedAuthors] = useState<AuthorInfo[]>([]);
  const [authorSearch, setAuthorSearch] = useState("");
  const [authorResults, setAuthorResults] = useState<AuthorInfo[]>([]);
  const [authorDropdownOpen, setAuthorDropdownOpen] = useState(false);
  const [authorSearching, setAuthorSearching] = useState(false);

  /* ---------- 字典数据 ---------- */
  const [styles, setStyles] = useState<DictionaryItem[]>([]);
  const [languages, setLanguages] = useState<DictionaryItem[]>([]);
  const [instruments, setInstruments] = useState<DictionaryItem[]>([]);
  const [emotionTags, setEmotionTags] = useState<DictionaryItem[]>([]);
  const [interestTags, setInterestTags] = useState<DictionaryItem[]>([]);

  const [submitting, setSubmitting] = useState(false);

  /* ---------- 图片预览 URL ---------- */
  const coverIconPreview = useFilePreview(coverIcon);
  const coverHomePreview = useFilePreview(coverHome);
  const coverPlayPreview = useFilePreview(coverPlay);

  /* ---------- 加载字典数据 ---------- */
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
        toast.error("加载字典数据失败");
      }
    };
    loadDict();
  }, []);

  /* ---------- 作者搜索（回车 / 按钮触发） ---------- */
  const doAuthorSearch = useCallback(
    async (q: string) => {
      if (!q.trim()) {
        setAuthorResults([]);
        return;
      }
      setAuthorSearching(true);
      try {
        const result = await api.searchUsers(q.trim(), 10, 0);
        setAuthorResults(
          result.items.map((u) => ({
            id: u.id,
            nickname: u.nickname,
            username: u.username,
          }))
        );
      } catch {
        toast.error("搜索用户失败");
      } finally {
        setAuthorSearching(false);
      }
    },
    [api]
  );

  /* ---------- 提交 ---------- */
  const handleSubmit = async () => {
    if (!title.trim() || !audioFile || !coverIcon) {
      toast.error("请填写歌名、上传音频文件和封面图标");
      return;
    }

    setSubmitting(true);
    try {
      await musicApi.adminImportMusic({
        title: title.trim(),
        audio_file: audioFile,
        cover_icon: coverIcon,
        is_vip: isVip,
        source: source || undefined,
        style_id: styleId ?? undefined,
        language_id: languageId ?? undefined,
        release_date: releaseDate || undefined,
        author_ids: selectedAuthors.length > 0 ? selectedAuthors.map((a) => a.id) : undefined,
        instrument_ids: instrumentIds.length > 0 ? instrumentIds : undefined,
        emotion_tag_ids: emotionTagIds.length > 0 ? emotionTagIds : undefined,
        interest_tag_ids: interestTagIds.length > 0 ? interestTagIds : undefined,
        cover_home: coverHome ?? undefined,
        cover_play: coverPlay ?? undefined,
        lyrics_file: lyricsFile ?? undefined,
      });
      toast.success("音乐导入成功");
      navigate("/admin/music");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "导入失败");
    } finally {
      setSubmitting(false);
    }
  };

  /* =========================================================================
     子组件：紧凑文件上传行（音频 / 歌词）
     ========================================================================= */
  const CompactFileRow = ({
    label,
    required,
    accept,
    icon: Icon,
    file,
    onChange,
  }: {
    label: string;
    required?: boolean;
    accept?: string;
    icon: React.ElementType;
    file: File | null;
    onChange: (f: File | null) => void;
  }) => {
    const [dragOver, setDragOver] = useState(false);
    return (
      <label style={{ display: "block", cursor: "pointer" }}>
        <div
          className={`import-compact-file-row ${dragOver ? "drag-over" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files[0];
            if (f) onChange(f);
          }}
        >
          <Icon size={16} className="file-icon" />
          {file ? (
            <>
              <span className="file-name">{file.name}</span>
              <button
                className="file-remove"
                onClick={(e) => { e.stopPropagation(); onChange(null); }}
                type="button"
              >
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              <span className="file-placeholder">
                {label}
                {required && <span style={{ color: "var(--color-danger)" }}> *</span>}
              </span>
              <span style={{ color: "var(--color-muted)", fontSize: 12, flexShrink: 0 }}>
                点击或拖拽上传
              </span>
            </>
          )}
          <input
            type="file"
            accept={accept}
            onChange={(e) => onChange(e.target.files?.[0] ?? null)}
            style={{ position: "absolute", opacity: 0, inset: 0, cursor: "pointer", width: "100%", height: "100%" }}
          />
        </div>
      </label>
    );
  };

  /* =========================================================================
     子组件：图片预览上传区
     ========================================================================= */
  const ImagePreviewZone = ({
    label,
    required,
    file,
    previewUrl,
    onChange,
    height,
  }: {
    label: string;
    required?: boolean;
    file: File | null;
    previewUrl: string | null;
    onChange: (f: File | null) => void;
    height?: number;
  }) => {
    const [dragOver, setDragOver] = useState(false);
    const h = height ?? 160;

    return (
      <label style={{ display: "block", cursor: "pointer" }}>
        <div
          className={`import-image-preview-zone ${dragOver ? "drag-over" : ""}`}
          style={{ height: h }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files[0];
            if (f) onChange(f);
          }}
        >
          {previewUrl ? (
            <>
              <img src={previewUrl} alt={label} className="preview-img" />
              <div className="preview-overlay">
                <span className="replace-hint">点击更换图片</span>
              </div>
              <button
                className="preview-remove"
                onClick={(e) => { e.stopPropagation(); onChange(null); }}
                type="button"
              >
                <X size={12} />
              </button>
            </>
          ) : (
            <div className="preview-placeholder">
              <ImageIcon size={24} color="var(--color-muted)" />
              <span className="placeholder-label">
                {label}
                {required && <span style={{ color: "var(--color-danger)" }}> *</span>}
              </span>
            </div>
          )}
          <input
            type="file"
            accept="image/*"
            onChange={(e) => onChange(e.target.files?.[0] ?? null)}
            style={{ position: "absolute", opacity: 0, inset: 0, cursor: "pointer", width: "100%", height: "100%" }}
          />
        </div>
      </label>
    );
  };

  /* =========================================================================
     子组件：搜索式选择（单选 / 多选通用）
     回车或点击搜索按钮后显示匹配结果
     ========================================================================= */
  const SearchableSelect = ({
    label,
    items,
    selectedIds,
    onToggle,
    mode = "multi",
    placeholder,
  }: {
    label: string;
    items: DictionaryItem[];
    selectedIds: number[];
    onToggle: (id: number) => void;
    mode?: "single" | "multi";
    placeholder?: string;
  }) => {
    const [search, setSearch] = useState("");
    const [results, setResults] = useState<DictionaryItem[]>([]);
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
          setDropdownOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const performSearch = () => {
      const q = search.trim().toLowerCase();
      if (!q) {
        setResults([]);
        setDropdownOpen(false);
        return;
      }
      const filtered = items
        .filter((i) => !selectedIds.includes(i.id))
        .filter((i) => i.name.toLowerCase().includes(q));
      setResults(filtered);
      setDropdownOpen(true);
    };

    const handleSelect = (item: DictionaryItem) => {
      if (mode === "single") {
        onToggle(item.id);
        setSearch("");
        setResults([]);
        setDropdownOpen(false);
      } else {
        onToggle(item.id);
        setSearch("");
        setResults([]);
        setDropdownOpen(false);
      }
    };

    const selectedItems = items.filter((i) => selectedIds.includes(i.id));

    return (
      <div ref={wrapperRef} style={{ position: "relative" }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
          {label}
        </label>
        <div className="import-search-inline">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                performSearch();
              }
            }}
            placeholder={placeholder ?? `搜索${label}...`}
            style={{ paddingLeft: 12 }}
          />
          <button
            className="import-search-trigger-btn"
            onClick={(e) => { e.preventDefault(); performSearch(); }}
            type="button"
            title="搜索"
          >
            <Search size={14} />
          </button>
        </div>
        <AnimatePresence>
          {dropdownOpen && results.length > 0 && (
            <motion.div
              className="import-search-dropdown"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
            >
              {results.map((item) => (
                <div
                  key={item.id}
                  className="import-search-dropdown-item"
                  onClick={() => handleSelect(item)}
                >
                  <span style={{ flex: 1 }}>{item.name}</span>
                  <Check size={14} style={{ color: "var(--color-muted)" }} />
                </div>
              ))}
            </motion.div>
          )}
          {dropdownOpen && search.trim() && results.length === 0 && (
            <motion.div
              className="import-search-dropdown"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
            >
              <div className="import-search-dropdown-item" style={{ color: "var(--color-muted)", cursor: "default" }}>
                未找到匹配的{label}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        {selectedItems.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            {selectedItems.map((item) => (
              <span key={item.id} className="import-tag-pill-removable">
                {item.name}
                <button
                  className="remove-btn"
                  onClick={() => onToggle(item.id)}
                  type="button"
                  title="移除"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    );
  };

  /* =========================================================================
     子组件：作者搜索选择
     ========================================================================= */
  const AuthorSelect = () => {
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      const handleClickOutside = (e: MouseEvent) => {
        if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
          setAuthorDropdownOpen(false);
        }
      };
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleSearch = () => {
      doAuthorSearch(authorSearch);
      setAuthorDropdownOpen(true);
    };

    const availableResults = authorResults.filter(
      (r) => !selectedAuthors.some((a) => a.id === r.id)
    );

    return (
      <div ref={wrapperRef}>
        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
          作者
        </label>
        <div className="import-search-inline">
          <input
            value={authorSearch}
            onChange={(e) => setAuthorSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSearch();
              }
            }}
            placeholder="搜索用户昵称或用户名..."
            style={{ paddingLeft: 12 }}
          />
          <button
            className="import-search-trigger-btn"
            onClick={(e) => { e.preventDefault(); handleSearch(); }}
            type="button"
            title="搜索"
            disabled={authorSearching}
          >
            <Search size={14} />
          </button>
        </div>
        <AnimatePresence>
          {authorDropdownOpen && (availableResults.length > 0 || authorSearching) && (
            <motion.div
              className="import-search-dropdown"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
            >
              {authorSearching && availableResults.length === 0 && (
                <div className="import-search-dropdown-item" style={{ color: "var(--color-muted)", cursor: "default" }}>
                  搜索中...
                </div>
              )}
              {availableResults.map((u) => (
                <div
                  key={u.id}
                  className="import-search-dropdown-item"
                  onClick={() => {
                    setSelectedAuthors((prev) => [...prev, u]);
                    setAuthorSearch("");
                    setAuthorDropdownOpen(false);
                  }}
                >
                  <User size={14} style={{ color: "var(--color-muted)", flexShrink: 0 }} />
                  <span style={{ flex: 1 }}>
                    {u.nickname}
                    <span style={{ color: "var(--color-muted)", marginLeft: 4 }}>@{u.username}</span>
                  </span>
                  <Check size={14} style={{ color: "var(--color-muted)" }} />
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        {selectedAuthors.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
            {selectedAuthors.map((a) => (
              <span key={a.id} className="import-tag-pill-removable">
                <User size={12} style={{ opacity: 0.7 }} />
                {a.nickname}
                <button
                  className="remove-btn"
                  onClick={() =>
                    setSelectedAuthors((prev) => prev.filter((x) => x.id !== a.id))
                  }
                  type="button"
                  title="移除"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>
    );
  };

  /* ========================================================================
     渲染
     ======================================================================== */
  return (
    <div>
      <FadeIn>
        <motion.button
          className="section-link"
          onClick={() => navigate("/admin/music")}
          whileHover={{ x: -4 }}
          style={{ display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 16 }}
        >
          <ArrowLeft size={16} /> 返回音乐列表
        </motion.button>
        <h1 className="page-title">导入音乐</h1>
      </FadeIn>

      <FadeIn delay={0.08}>
        <div className="import-form-grid">
          {/* ========== 左栏：主要内容 ========== */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* 基本信息 */}
            <div className="import-section">
              <h3 className="import-section-title">基本信息</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <label>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
                    歌名 <span style={{ color: "var(--color-danger)" }}>*</span>
                  </span>
                  <input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="请输入歌曲名称"
                    style={{ fontSize: 14 }}
                  />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <label>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
                      来源
                    </span>
                    <input
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                      placeholder="如：网易云音乐、原创"
                      style={{ fontSize: 14 }}
                    />
                  </label>
                  <label>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
                      发行日期
                    </span>
                    <input type="date" value={releaseDate} onChange={(e) => setReleaseDate(e.target.value)} style={{ fontSize: 14 }} />
                  </label>
                </div>
              </div>
            </div>

            {/* 媒体文件 */}
            <div className="import-section">
              <h3 className="import-section-title">媒体文件</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <CompactFileRow
                  label="音频文件"
                  required
                  accept="audio/mpeg,audio/mp3,audio/flac,audio/wav,audio/ogg,audio/aac"
                  icon={Music}
                  file={audioFile}
                  onChange={setAudioFile}
                />
                <CompactFileRow
                  label="歌词文件"
                  accept=".lrc,.txt"
                  icon={FileText}
                  file={lyricsFile}
                  onChange={setLyricsFile}
                />
              </div>
            </div>

            {/* 封面图片 */}
            <div className="import-section">
              <h3 className="import-section-title">封面图片</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <ImagePreviewZone
                  label="封面图标"
                  required
                  file={coverIcon}
                  previewUrl={coverIconPreview}
                  onChange={setCoverIcon}
                  height={180}
                />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <ImagePreviewZone
                    label="封面 Home"
                    file={coverHome}
                    previewUrl={coverHomePreview}
                    onChange={setCoverHome}
                    height={120}
                  />
                  <ImagePreviewZone
                    label="封面 Play"
                    file={coverPlay}
                    previewUrl={coverPlayPreview}
                    onChange={setCoverPlay}
                    height={120}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* ========== 右栏：元信息 ========== */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* 分类 */}
            <div className="import-section">
              <h3 className="import-section-title">分类</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <SearchableSelect
                  label="风格"
                  items={styles}
                  selectedIds={styleId !== null ? [styleId] : []}
                  onToggle={(id) => setStyleId(styleId === id ? null : id)}
                  mode="single"
                  placeholder="搜索风格..."
                />
                <SearchableSelect
                  label="语言"
                  items={languages}
                  selectedIds={languageId !== null ? [languageId] : []}
                  onToggle={(id) => setLanguageId(languageId === id ? null : id)}
                  mode="single"
                  placeholder="搜索语言..."
                />
                <label className="import-toggle">
                  <input
                    type="checkbox"
                    checked={isVip}
                    onChange={(e) => setIsVip(e.target.checked)}
                  />
                  <span className="import-toggle-switch" />
                  <span>VIP 专属</span>
                </label>
              </div>
            </div>

            {/* 标签 */}
            <div className="import-section">
              <h3 className="import-section-title">标签</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <SearchableSelect
                  label="乐器"
                  items={instruments}
                  selectedIds={instrumentIds}
                  onToggle={(id) => {
                    setInstrumentIds((prev) =>
                      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                    );
                  }}
                  mode="multi"
                  placeholder="搜索乐器..."
                />
                <SearchableSelect
                  label="情感标签"
                  items={emotionTags}
                  selectedIds={emotionTagIds}
                  onToggle={(id) => {
                    setEmotionTagIds((prev) =>
                      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                    );
                  }}
                  mode="multi"
                  placeholder="搜索情感标签..."
                />
                <SearchableSelect
                  label="兴趣标签"
                  items={interestTags}
                  selectedIds={interestTagIds}
                  onToggle={(id) => {
                    setInterestTagIds((prev) =>
                      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
                    );
                  }}
                  mode="multi"
                  placeholder="搜索兴趣标签..."
                />
              </div>
            </div>

            {/* 作者 */}
            <div className="import-section">
              <h3 className="import-section-title">作者</h3>
              <AuthorSelect />
            </div>
          </div>
        </div>

        {/* 提交按钮 */}
        <div style={{ marginTop: 24 }}>
          <motion.button
            className="primary-button"
            onClick={handleSubmit}
            disabled={submitting}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ minWidth: 140 }}
          >
            {submitting ? "导入中..." : "确认导入"}
          </motion.button>
        </div>
      </FadeIn>
    </div>
  );
};
