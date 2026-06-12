import { useState, useEffect, useMemo } from "react";
import { Search, X } from "lucide-react";
import { motion } from "framer-motion";
import { dictionaryApi } from "../../shared/api/instances";
import type { DictionaryType, DictionaryItem } from "../../shared/api/types";

interface TagSelectorProps {
  /** 字典类型（styles / languages / instruments / emotion_tags / interest_tags）。 */
  dictionaryType: DictionaryType;
  /** 当前选中的 ID 列表。 */
  selectedIds: number[];
  /** 选中变化回调。 */
  onChange: (ids: number[]) => void;
  /** 是否多选，默认 true。 */
  multi?: boolean;
  /** 筛选组标题。 */
  label: string;
  /** 品牌色 accent 名（用于高亮色）。 */
  accent?: string;
  /** 是否禁用。 */
  disabled?: boolean;
}

const DISPLAY_LIMIT = 15;

export const TagSelector = ({
  dictionaryType,
  selectedIds,
  onChange,
  multi = true,
  label,
  accent = "coral",
  disabled = false,
}: TagSelectorProps) => {
  const [allTags, setAllTags] = useState<DictionaryItem[]>([]);
  const [search, setSearch] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    dictionaryApi
      .listDictionary(dictionaryType, 200, 0)
      .then((res) => {
        if (!cancelled) {
          setAllTags(res.items ?? []);
          setLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dictionaryType]);

  const filtered = useMemo(() => {
    if (!search.trim()) return allTags;
    const q = search.trim().toLowerCase();
    return allTags.filter((t) => t.name.toLowerCase().includes(q));
  }, [allTags, search]);

  const visibleTags = showAll ? filtered : filtered.slice(0, DISPLAY_LIMIT);
  const hasMore = filtered.length > DISPLAY_LIMIT && !showAll;

  const handleToggle = (id: number) => {
    if (disabled) return;
    if (multi) {
      const next = selectedIds.includes(id)
        ? selectedIds.filter((v) => v !== id)
        : [...selectedIds, id];
      onChange(next);
    } else {
      onChange(selectedIds.includes(id) ? [] : [id]);
    }
  };

  const handleClearSearch = () => setSearch("");

  return (
    <div className="tag-selector">
      <div className="tag-selector-header">
        <span className="tag-selector-label">{label}</span>
        {selectedIds.length > 0 && (
          <button
            type="button"
            className="tag-selector-clear"
            onClick={() => onChange([])}
            disabled={disabled}
          >
            <X size={11} />
            清除
          </button>
        )}
      </div>

      {/* 搜索框 */}
      <div className="tag-selector-search-wrap">
        <Search size={13} className="tag-selector-search-icon" />
        <input
          type="text"
          className="tag-selector-search"
          placeholder="搜索..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setShowAll(true);
          }}
          disabled={disabled}
        />
        {search && (
          <button
            type="button"
            className="tag-selector-search-clear"
            onClick={handleClearSearch}
          >
            <X size={12} />
          </button>
        )}
      </div>

      {/* 标签列表 */}
      {!loaded ? (
        <div className="tag-selector-loading">加载中...</div>
      ) : filtered.length === 0 ? (
        <div className="tag-selector-empty">无匹配标签</div>
      ) : (
        <div className="tag-selector-list">
          {visibleTags.map((tag) => {
            const active = selectedIds.includes(tag.id);
            return (
              <motion.button
                key={tag.id}
                type="button"
                className={`tag-selector-pill${active ? " active" : ""}`}
                style={
                  active
                    ? { backgroundColor: `var(--color-brand-${accent})`, borderColor: `var(--color-brand-${accent})`, color: accent === "coral" || accent === "pink" || accent === "teal" ? "white" : "var(--color-ink)" }
                    : undefined
                }
                onClick={() => handleToggle(tag.id)}
                whileTap={{ scale: 0.95 }}
                disabled={disabled}
              >
                {tag.name}
              </motion.button>
            );
          })}
          {hasMore && (
            <button
              type="button"
              className="tag-selector-more"
              onClick={() => setShowAll(true)}
            >
              显示全部 ({filtered.length})
            </button>
          )}
        </div>
      )}
    </div>
  );
};
