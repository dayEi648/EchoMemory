import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { Search, SlidersHorizontal, X, ChevronDown, ArrowRight } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { TagSelector } from "./TagSelector";
import { dictionaryApi } from "../../shared/api/instances";
import type { DictionaryItem } from "../../shared/api/types";

export interface BrowseFilters {
  q: string;
  style_id: number | null;
  language_id: number | null;
  instrument_ids: number[];
  emotion_tag_ids: number[];
  interest_tag_ids: number[];
  release_date_from: string;
  release_date_to: string;
}

export const EMPTY_FILTERS: BrowseFilters = {
  q: "",
  style_id: null,
  language_id: null,
  instrument_ids: [],
  emotion_tag_ids: [],
  interest_tag_ids: [],
  release_date_from: "",
  release_date_to: "",
};

type BrowseTab = "music" | "albums" | "playlists";

interface BrowseFilterPanelProps {
  tab: BrowseTab;
  filters: BrowseFilters;
  onFiltersChange: (filters: BrowseFilters) => void;
  onApply: () => void;
  onReset: () => void;
  loading?: boolean;
}

/** 各 tab 的快速筛选 chip 字典类型配置 */
const QUICK_CHIP_CONFIG: Record<BrowseTab, { type: "styles" | "languages" | "emotion_tags"; label: string }[]> = {
  music: [
    { type: "styles", label: "风格" },
    { type: "languages", label: "语言" },
    { type: "emotion_tags", label: "情绪" },
  ],
  albums: [
    { type: "emotion_tags", label: "情绪" },
  ],
  playlists: [
    { type: "emotion_tags", label: "情绪" },
  ],
};

const QUICK_CHIP_LIMIT = 8;

export const BrowseFilterPanel = ({
  tab,
  filters,
  onFiltersChange,
  onApply,
  onReset,
  loading = false,
}: BrowseFilterPanelProps) => {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [quickTags, setQuickTags] = useState<Record<string, DictionaryItem[]>>({});
  const searchRef = useRef<HTMLInputElement>(null);

  const update = useCallback(
    (patch: Partial<BrowseFilters>) => onFiltersChange({ ...filters, ...patch }),
    [filters, onFiltersChange],
  );

  // 加载快速筛选标签
  useEffect(() => {
    const configs = QUICK_CHIP_CONFIG[tab];
    const typeSet = new Set(configs.map((c) => c.type));
    const result: Record<string, DictionaryItem[]> = {};

    Promise.all(
      [...typeSet].map((type) =>
        dictionaryApi
          .listDictionary(type, 30, 0)
          .then((res) => {
            result[type] = res.items ?? [];
          })
          .catch(() => {
            result[type] = [];
          }),
      ),
    ).then(() => setQuickTags(result));
  }, [tab]);

  // 统计激活的筛选数量
  const activeCount = useMemo(() => {
    let n = 0;
    if (filters.q) n++;
    if (filters.style_id != null) n++;
    if (filters.language_id != null) n++;
    if (filters.instrument_ids.length > 0) n++;
    if (filters.emotion_tag_ids.length > 0) n++;
    if (filters.interest_tag_ids.length > 0) n++;
    if (filters.release_date_from || filters.release_date_to) n++;
    return n;
  }, [filters]);

  // 快速 chip 点击 —— 仅更新状态，不查询
  const handleQuickChip = (configType: string, tagId: number) => {
    if (configType === "styles") {
      update({ style_id: filters.style_id === tagId ? null : tagId });
    } else if (configType === "languages") {
      update({ language_id: filters.language_id === tagId ? null : tagId });
    } else if (configType === "emotion_tags") {
      update({
        emotion_tag_ids: filters.emotion_tag_ids.includes(tagId)
          ? filters.emotion_tag_ids.filter((id) => id !== tagId)
          : [...filters.emotion_tag_ids, tagId],
      });
    }
  };

  // 判断某个 chip 是否激活
  const isChipActive = (configType: string, tagId: number): boolean => {
    if (configType === "styles") return filters.style_id === tagId;
    if (configType === "languages") return filters.language_id === tagId;
    if (configType === "emotion_tags") return filters.emotion_tag_ids.includes(tagId);
    return false;
  };

  const placeholder =
    tab === "music" ? "搜索歌曲标题..." : tab === "albums" ? "搜索专辑标题..." : "搜索歌单标题...";

  return (
    <div className="browse-filter-bar">
      {/* 搜索栏 */}
      <div className="browse-search-bar">
        <div className="browse-search-bar-input">
          <Search size={16} className="browse-search-bar-icon" />
          <input
            ref={searchRef}
            type="text"
            placeholder={placeholder}
            value={filters.q}
            onChange={(e) => update({ q: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter") onApply();
            }}
            disabled={loading}
          />
          {filters.q && (
            <button
              type="button"
              className="browse-search-bar-clear"
              onClick={() => update({ q: "" })}
            >
              <X size={14} />
            </button>
          )}
          <motion.button
            type="button"
            className="browse-search-bar-submit"
            onClick={() => onApply()}
            disabled={loading}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.95 }}
            title="搜索"
          >
            <ArrowRight size={16} />
          </motion.button>
        </div>

        <motion.button
          type="button"
          className={`browse-advanced-toggle${advancedOpen ? " open" : ""}${activeCount > 0 ? " has-active" : ""}`}
          onClick={() => setAdvancedOpen(!advancedOpen)}
          whileTap={{ scale: 0.96 }}
        >
          <SlidersHorizontal size={14} />
          筛选
          {activeCount > 0 && <span className="browse-advanced-badge">{activeCount}</span>}
          <motion.span
            animate={{ rotate: advancedOpen ? 180 : 0 }}
            transition={{ duration: 0.25 }}
            style={{ display: "inline-flex" }}
          >
            <ChevronDown size={12} />
          </motion.span>
        </motion.button>
      </div>

      {/* 快速标签芯片行 */}
      <div className="browse-quick-chips">
        {QUICK_CHIP_CONFIG[tab].map((config) => {
          const tags = quickTags[config.type]?.slice(0, QUICK_CHIP_LIMIT) ?? [];
          if (tags.length === 0) return null;
          return (
            <div key={config.type} className="browse-quick-chip-group">
              <span className="browse-quick-chip-label">{config.label}</span>
              {tags.map((tag) => {
                const active = isChipActive(config.type, tag.id);
                return (
                  <motion.button
                    key={tag.id}
                    type="button"
                    className={`browse-quick-chip${active ? " active" : ""}`}
                    onClick={() => handleQuickChip(config.type, tag.id)}
                    whileTap={{ scale: 0.93 }}
                    disabled={loading}
                  >
                    {tag.name}
                  </motion.button>
                );
              })}
            </div>
          );
        })}
      </div>

      {/* 高级筛选面板 */}
      <AnimatePresence>
        {advancedOpen && (
          <motion.div
            className="browse-advanced-panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div className="browse-advanced-inner">
              {tab === "music" && (
                <>
                  <div className="browse-advanced-grid">
                    <TagSelector
                      dictionaryType="styles"
                      selectedIds={filters.style_id != null ? [filters.style_id] : []}
                      onChange={(ids) => update({ style_id: ids.length > 0 ? ids[0] : null })}
                      multi={false}
                      label="风格"
                      accent="lavender"
                      disabled={loading}
                    />
                    <TagSelector
                      dictionaryType="languages"
                      selectedIds={filters.language_id != null ? [filters.language_id] : []}
                      onChange={(ids) => update({ language_id: ids.length > 0 ? ids[0] : null })}
                      multi={false}
                      label="语言"
                      accent="mint"
                      disabled={loading}
                    />
                    <TagSelector
                      dictionaryType="instruments"
                      selectedIds={filters.instrument_ids}
                      onChange={(ids) => update({ instrument_ids: ids })}
                      multi
                      label="乐器"
                      accent="peach"
                      disabled={loading}
                    />
                    <TagSelector
                      dictionaryType="emotion_tags"
                      selectedIds={filters.emotion_tag_ids}
                      onChange={(ids) => update({ emotion_tag_ids: ids })}
                      multi
                      label="情绪标签"
                      accent="pink"
                      disabled={loading}
                    />
                    <TagSelector
                      dictionaryType="interest_tags"
                      selectedIds={filters.interest_tag_ids}
                      onChange={(ids) => update({ interest_tag_ids: ids })}
                      multi
                      label="兴趣标签"
                      accent="ochre"
                      disabled={loading}
                    />
                  </div>
                  <div className="browse-advanced-date">
                    <span className="browse-advanced-section-label">发行日期</span>
                    <div className="browse-date-range">
                      <input
                        type="date"
                        className="browse-date-input"
                        value={filters.release_date_from}
                        onChange={(e) => update({ release_date_from: e.target.value })}
                        disabled={loading}
                      />
                      <span style={{ color: "var(--color-muted)", fontSize: 13 }}>至</span>
                      <input
                        type="date"
                        className="browse-date-input"
                        value={filters.release_date_to}
                        onChange={(e) => update({ release_date_to: e.target.value })}
                        disabled={loading}
                      />
                    </div>
                  </div>
                </>
              )}

              {(tab === "albums" || tab === "playlists") && (
                <div className="browse-advanced-grid">
                  <TagSelector
                    dictionaryType="emotion_tags"
                    selectedIds={filters.emotion_tag_ids}
                    onChange={(ids) => update({ emotion_tag_ids: ids })}
                    multi
                    label="情绪标签"
                    accent="pink"
                    disabled={loading}
                  />
                  <TagSelector
                    dictionaryType="interest_tags"
                    selectedIds={filters.interest_tag_ids}
                    onChange={(ids) => update({ interest_tag_ids: ids })}
                    multi
                    label="兴趣标签"
                    accent="ochre"
                    disabled={loading}
                  />
                </div>
              )}

              <div className="browse-advanced-actions">
                <span className="browse-advanced-hint">
                  设置筛选条件后，点击上方搜索按钮查询
                </span>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => {
                    onReset();
                    setAdvancedOpen(false);
                  }}
                  disabled={loading}
                >
                  重置全部
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
