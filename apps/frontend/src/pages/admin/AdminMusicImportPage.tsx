import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Music, FileText } from "lucide-react";

import { musicApi, dictionaryApi } from "../../shared/api/instances";
import { useAuthStore } from "../../shared/stores/authStore";
import { getApiErrorMessage } from "../../shared/apiError";
import type { DictionaryItem } from "../../shared/api/types";
import { FadeIn } from "../../components/motion/FadeIn";
import {
  CompactFileRow,
  ImagePreviewZone,
  SearchableTagSelect,
  AuthorSelect,
  type AuthorInfo,
} from "./_musicFormComponents";

/**
 * 导入音乐页面。
 *
 * 采用双栏响应式布局，与编辑弹窗共用组件以保持视觉一致。
 */
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

  /* ---------- 分类 ---------- */
  const [styleId, setStyleId] = useState<number | null>(null);
  const [languageId, setLanguageId] = useState<number | null>(null);

  /* ---------- 标签 ---------- */
  const [instrumentIds, setInstrumentIds] = useState<number[]>([]);
  const [emotionTagIds, setEmotionTagIds] = useState<number[]>([]);
  const [interestTagIds, setInterestTagIds] = useState<number[]>([]);

  /* ---------- 作者 ---------- */
  const [selectedAuthors, setSelectedAuthors] = useState<AuthorInfo[]>([]);

  /* ---------- 字典数据 ---------- */
  const [styles, setStyles] = useState<DictionaryItem[]>([]);
  const [languages, setLanguages] = useState<DictionaryItem[]>([]);
  const [instruments, setInstruments] = useState<DictionaryItem[]>([]);
  const [emotionTags, setEmotionTags] = useState<DictionaryItem[]>([]);
  const [interestTags, setInterestTags] = useState<DictionaryItem[]>([]);

  const [submitting, setSubmitting] = useState(false);

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
      toast.error(getApiErrorMessage(err, "导入失败"));
    } finally {
      setSubmitting(false);
    }
  };

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
            <div className="warm-panel">
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
            <div className="warm-panel">
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
            <div className="warm-panel">
              <h3 className="import-section-title">封面图片</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <ImagePreviewZone
                  label="封面图标"
                  required
                  file={coverIcon}
                  onChange={setCoverIcon}
                  height={180}
                />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <ImagePreviewZone
                    label="封面 Home"
                    file={coverHome}
                    onChange={setCoverHome}
                    height={120}
                  />
                  <ImagePreviewZone
                    label="封面 Play"
                    file={coverPlay}
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
            <div className="warm-panel">
              <h3 className="import-section-title">分类</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <SearchableTagSelect
                  label="风格"
                  items={styles}
                  selectedIds={styleId !== null ? [styleId] : []}
                  onToggle={(id) => setStyleId(styleId === id ? null : id)}
                  mode="single"
                  placeholder="搜索风格..."
                />
                <SearchableTagSelect
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
            <div className="warm-panel">
              <h3 className="import-section-title">标签</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <SearchableTagSelect
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
                <SearchableTagSelect
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
                <SearchableTagSelect
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
            <div className="warm-panel">
              <h3 className="import-section-title">作者</h3>
              <AuthorSelect
                selectedAuthors={selectedAuthors}
                onChange={setSelectedAuthors}
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
