import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Upload, Music, X, Search } from "lucide-react";

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

export const AdminMusicImportPage = () => {
  const navigate = useNavigate();
  const { api } = useAuthStore();

  const [title, setTitle] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [coverIcon, setCoverIcon] = useState<File | null>(null);
  const [coverHome, setCoverHome] = useState<File | null>(null);
  const [coverPlay, setCoverPlay] = useState<File | null>(null);
  const [lyricsFile, setLyricsFile] = useState<File | null>(null);
  const [isVip, setIsVip] = useState(false);
  const [source, setSource] = useState("");
  const [releaseDate, setReleaseDate] = useState("");
  const [styleId, setStyleId] = useState<number | "">("");
  const [languageId, setLanguageId] = useState<number | "">("");
  const [instrumentIds, setInstrumentIds] = useState<number[]>([]);
  const [emotionTagIds, setEmotionTagIds] = useState<number[]>([]);
  const [interestTagIds, setInterestTagIds] = useState<number[]>([]);
  const [authorIds, setAuthorIds] = useState<number[]>([]);
  const [authorSearch, setAuthorSearch] = useState("");
  const [authorResults, setAuthorResults] = useState<{ id: number; nickname: string; username: string }[]>([]);

  const [styles, setStyles] = useState<DictionaryItem[]>([]);
  const [languages, setLanguages] = useState<DictionaryItem[]>([]);
  const [instruments, setInstruments] = useState<DictionaryItem[]>([]);
  const [emotionTags, setEmotionTags] = useState<DictionaryItem[]>([]);
  const [interestTags, setInterestTags] = useState<DictionaryItem[]>([]);

  const [submitting, setSubmitting] = useState(false);

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

  const handleAuthorSearch = async () => {
    if (!authorSearch.trim()) return;
    try {
      const users = await api.searchUsers(authorSearch.trim());
      setAuthorResults(users.map((u) => ({ id: u.id, nickname: u.nickname, username: u.username })));
    } catch {
      toast.error("搜索用户失败");
    }
  };

  const handleSubmit = async () => {
    if (!title.trim() || !audioFile || !coverIcon) {
      toast.error("请填写歌名、上传音频文件和封面");
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
        style_id: styleId ? Number(styleId) : undefined,
        language_id: languageId ? Number(languageId) : undefined,
        release_date: releaseDate || undefined,
        author_ids: authorIds.length > 0 ? authorIds : undefined,
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

  const FileInput = ({
    label,
    required,
    accept,
    onChange,
    file,
  }: {
    label: string;
    required?: boolean;
    accept?: string;
    onChange: (f: File | null) => void;
    file: File | null;
  }) => (
    <label style={{ position: "relative" }}>
      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
        {label}
        {required && <span style={{ color: "var(--color-danger)" }}>*</span>}
      </span>
      <div
        style={{
          border: "2px dashed var(--color-border)",
          borderRadius: 10,
          padding: 20,
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color 0.2s",
          position: "relative",
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.currentTarget.style.borderColor = "var(--color-ink)";
        }}
        onDragLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--color-border)";
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.currentTarget.style.borderColor = "var(--color-border)";
          const f = e.dataTransfer.files[0];
          if (f) onChange(f);
        }}
      >
        {file ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
            <span style={{ fontSize: 13 }}>{file.name}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              style={{ background: "none", border: "none", cursor: "pointer", padding: 2 }}
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <>
            <Upload size={24} color="var(--color-muted)" />
            <p style={{ fontSize: 13, color: "var(--color-muted)", margin: "8px 0 0" }}>
              点击或拖拽文件到此处
            </p>
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
        <div className="form-stack" style={{ maxWidth: 640 }}>
          <label>
            歌名 <span style={{ color: "var(--color-danger)" }}>*</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="请输入歌曲名称" />
          </label>

          <FileInput
            label="音频文件"
            required
            accept="audio/mpeg,audio/mp3,audio/flac,audio/wav,audio/ogg,audio/aac"
            file={audioFile}
            onChange={setAudioFile}
          />

          <FileInput
            label="封面图标"
            required
            accept="image/*"
            file={coverIcon}
            onChange={setCoverIcon}
          />

          <FileInput
            label="封面 Home（可选）"
            accept="image/*"
            file={coverHome}
            onChange={setCoverHome}
          />

          <FileInput
            label="封面 Play（可选）"
            accept="image/*"
            file={coverPlay}
            onChange={setCoverPlay}
          />

          <FileInput
            label="歌词文件（可选）"
            accept=".lrc,.txt"
            file={lyricsFile}
            onChange={setLyricsFile}
          />

          <label>
            来源
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="如：网易云音乐、原创" />
          </label>

          <label>
            发行日期
            <input type="date" value={releaseDate} onChange={(e) => setReleaseDate(e.target.value)} />
          </label>

          <label>
            风格
            <select
              value={String(styleId)}
              onChange={(e) => setStyleId(e.target.value ? Number(e.target.value) : "")}
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
              value={String(languageId)}
              onChange={(e) => setLanguageId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">无</option>
              {languages.map((l) => (
                <option key={l.id} value={String(l.id)}>{l.name}</option>
              ))}
            </select>
          </label>

          <label>
            乐器
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {instruments.map((inst) => (
                <label
                  key={inst.id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 20,
                    background: instrumentIds.includes(inst.id) ? "var(--color-ink)" : "var(--color-border)",
                    color: instrumentIds.includes(inst.id) ? "white" : "var(--color-ink)",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={instrumentIds.includes(inst.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setInstrumentIds((prev) => [...prev, inst.id]);
                      } else {
                        setInstrumentIds((prev) => prev.filter((id) => id !== inst.id));
                      }
                    }}
                    style={{ display: "none" }}
                  />
                  {inst.name}
                </label>
              ))}
            </div>
          </label>

          <label>
            情感标签
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {emotionTags.map((tag) => (
                <label
                  key={tag.id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 20,
                    background: emotionTagIds.includes(tag.id) ? "var(--color-ink)" : "var(--color-border)",
                    color: emotionTagIds.includes(tag.id) ? "white" : "var(--color-ink)",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={emotionTagIds.includes(tag.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setEmotionTagIds((prev) => [...prev, tag.id]);
                      } else {
                        setEmotionTagIds((prev) => prev.filter((id) => id !== tag.id));
                      }
                    }}
                    style={{ display: "none" }}
                  />
                  {tag.name}
                </label>
              ))}
            </div>
          </label>

          <label>
            兴趣标签
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {interestTags.map((tag) => (
                <label
                  key={tag.id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 20,
                    background: interestTagIds.includes(tag.id) ? "var(--color-ink)" : "var(--color-border)",
                    color: interestTagIds.includes(tag.id) ? "white" : "var(--color-ink)",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={interestTagIds.includes(tag.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setInterestTagIds((prev) => [...prev, tag.id]);
                      } else {
                        setInterestTagIds((prev) => prev.filter((id) => id !== tag.id));
                      }
                    }}
                    style={{ display: "none" }}
                  />
                  {tag.name}
                </label>
              ))}
            </div>
          </label>

          <label>
            作者
            <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
              <input
                value={authorSearch}
                onChange={(e) => setAuthorSearch(e.target.value)}
                placeholder="搜索用户昵称..."
                style={{ flex: 1 }}
                onKeyDown={(e) => e.key === "Enter" && handleAuthorSearch()}
              />
              <motion.button
                className="ghost-button"
                onClick={handleAuthorSearch}
                whileTap={{ scale: 0.97 }}
                type="button"
              >
                <Search size={14} />
              </motion.button>
            </div>
            {authorResults.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 8 }}>
                {authorResults.map((u) => (
                  <motion.button
                    key={u.id}
                    className="ghost-button"
                    onClick={() => {
                      if (!authorIds.includes(u.id)) {
                        setAuthorIds((prev) => [...prev, u.id]);
                      }
                      setAuthorResults([]);
                      setAuthorSearch("");
                    }}
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    type="button"
                    style={{ fontSize: 12 }}
                  >
                    + {u.nickname}
                  </motion.button>
                ))}
              </div>
            )}
            {authorIds.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {authorIds.map((id) => (
                  <span
                    key={id}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "4px 10px",
                      borderRadius: 20,
                      background: "var(--color-ink)",
                      color: "white",
                      fontSize: 12,
                    }}
                  >
                    ID: {id}
                    <button
                      onClick={() => setAuthorIds((prev) => prev.filter((i) => i !== id))}
                      style={{ background: "none", border: "none", cursor: "pointer", color: "white", padding: 0 }}
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={isVip}
              onChange={(e) => setIsVip(e.target.checked)}
            />
            <span>VIP 专属</span>
          </label>

          <motion.button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={submitting}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            type="button"
            style={{ marginTop: 16 }}
          >
            {submitting ? "导入中..." : "确认导入"}
          </motion.button>
        </div>
      </FadeIn>
    </div>
  );
};
