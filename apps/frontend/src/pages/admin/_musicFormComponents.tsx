/**
 * 音乐表单共享组件。
 *
 * 供「导入音乐」和「编辑音乐」弹窗复用，保持视觉与交互一致性。
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Image as ImageIcon,
  X,
  Search,
  User,
  Check,
} from "lucide-react";
import type { DictionaryItem } from "../../shared/api/types";

/* ======================================================================== */
export interface AuthorInfo {
  id: number;
  nickname: string;
  username: string;
}

/* ======================================================================== */
/** Hook：为 File 对象创建临时预览 URL，并在组件卸载时自动释放。 */
export const useFilePreview = (file: File | null) => {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => { URL.revokeObjectURL(url); };
  }, [file]);
  return preview;
};

/* ======================================================================== */
/** 从 URL 中提取文件名（用于显示当前已上传的文件）。 */
const fileNameFromUrl = (url: string | null | undefined): string | null => {
  if (!url) return null;
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/");
    return parts[parts.length - 1] || null;
  } catch {
    return null;
  }
};

/* ======================================================================== */
/**
 * 紧凑文件上传行（音频 / 歌词）。
 *
 * - 无文件时显示占位提示
 * - 有当前文件时显示文件名（不可删除，仅可替换）
 * - 选择了新文件时显示新文件名 + 删除按钮（取消替换）
 */
export const CompactFileRow = ({
  label,
  required,
  accept,
  icon: Icon,
  file,
  existingUrl,
  onChange,
}: {
  label: string;
  required?: boolean;
  accept?: string;
  icon: React.ElementType;
  file: File | null;
  existingUrl?: string | null;
  onChange: (f: File | null) => void;
}) => {
  const [dragOver, setDragOver] = useState(false);
  const existingName = fileNameFromUrl(existingUrl);
  const displayName = file?.name ?? existingName;

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
        {displayName ? (
          <>
            <span className="file-name">
              {file ? "替换为：" : "当前："}{displayName}
            </span>
            <button
              className="file-remove"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              type="button"
              title={file ? "取消替换" : "移除"}
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

/* ======================================================================== */
/**
 * 图片预览上传区。
 *
 * - 无文件且无当前图片时显示占位
 * - 有当前图片时显示缩略图，hover 显示"点击替换"
 * - 选择了新文件时显示新图片预览
 */
export const ImagePreviewZone = ({
  label,
  required,
  file,
  existingUrl,
  onChange,
  height = 160,
}: {
  label: string;
  required?: boolean;
  file: File | null;
  existingUrl?: string | null;
  onChange: (f: File | null) => void;
  height?: number;
}) => {
  const [dragOver, setDragOver] = useState(false);
  const previewUrl = useFilePreview(file);
  const displayUrl = previewUrl ?? existingUrl ?? null;

  return (
    <label style={{ display: "block", cursor: "pointer" }}>
      <div
        className={`import-image-preview-zone ${dragOver ? "drag-over" : ""}`}
        style={{ height }}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files[0];
          if (f) onChange(f);
        }}
      >
        {displayUrl ? (
          <>
            <img src={displayUrl} alt={label} className="preview-img" />
            <div className="preview-overlay">
              <span className="replace-hint">
                {file ? "新图片 — 点击更换" : "点击替换图片"}
              </span>
            </div>
            <button
              className="preview-remove"
              onClick={(e) => { e.stopPropagation(); onChange(null); }}
              type="button"
              title={file ? "取消替换" : "移除"}
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

/* ======================================================================== */
/**
 * 搜索式选择（单选 / 多选）。
 *
 * 回车或点击搜索按钮后才显示匹配结果。
 */
export const SearchableTagSelect = ({
  label,
  items,
  selectedIds,
  onToggle,
  mode = "multi",
  placeholder,
  showLabel = true,
}: {
  label: string;
  items: DictionaryItem[];
  selectedIds: number[];
  onToggle: (id: number) => void;
  mode?: "single" | "multi";
  placeholder?: string;
  showLabel?: boolean;
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
      {showLabel && (
        <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
          {label}
        </label>
      )}
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
          style={{ paddingLeft: 12, fontSize: 13 }}
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

/* ======================================================================== */
/**
 * 作者搜索选择（多选）。
 *
 * 回车或点击搜索按钮后查询用户，下拉显示匹配结果。
 */
export const AuthorSelect = ({
  selectedAuthors,
  onChange,
  searchUsers,
}: {
  selectedAuthors: AuthorInfo[];
  onChange: (authors: AuthorInfo[]) => void;
  searchUsers: (q: string) => Promise<{ items: { id: number; nickname: string; username: string }[] } | undefined>;
}) => {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<AuthorInfo[]>([]);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searching, setSearching] = useState(false);
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

  const handleSearch = useCallback(async () => {
    if (!search.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const result = await searchUsers(search.trim());
      if (result) {
        setResults(
          result.items.map((u) => ({ id: u.id, nickname: u.nickname, username: u.username }))
        );
      }
    } catch {
      toast.error("搜索用户失败");
    } finally {
      setSearching(false);
    }
  }, [search, searchUsers]);

  const availableResults = results.filter(
    (r) => !selectedAuthors.some((a) => a.id === r.id)
  );

  return (
    <div ref={wrapperRef}>
      <label style={{ fontSize: 13, fontWeight: 600, color: "var(--color-ink)", display: "block", marginBottom: 6 }}>
        作者
      </label>
      <div className="import-search-inline">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleSearch();
              setDropdownOpen(true);
            }
          }}
          placeholder="搜索用户昵称或用户名..."
          style={{ paddingLeft: 12, fontSize: 13 }}
        />
        <button
          className="import-search-trigger-btn"
          onClick={(e) => { e.preventDefault(); handleSearch(); setDropdownOpen(true); }}
          type="button"
          title="搜索"
          disabled={searching}
        >
          <Search size={14} />
        </button>
      </div>
      <AnimatePresence>
        {dropdownOpen && (availableResults.length > 0 || searching) && (
          <motion.div
            className="import-search-dropdown"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
          >
            {searching && availableResults.length === 0 && (
              <div className="import-search-dropdown-item" style={{ color: "var(--color-muted)", cursor: "default" }}>
                搜索中...
              </div>
            )}
            {availableResults.map((u) => (
              <div
                key={u.id}
                className="import-search-dropdown-item"
                onClick={() => {
                  onChange([...selectedAuthors, u]);
                  setSearch("");
                  setDropdownOpen(false);
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
                onClick={() => onChange(selectedAuthors.filter((x) => x.id !== a.id))}
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
