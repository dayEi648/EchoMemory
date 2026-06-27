import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Trash2,
  Upload,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";

import { musicKnowledgeApi } from "../../shared/api/instances";
import { getApiErrorMessage } from "../../shared/apiError";
import { EmptyState } from "../../components/ui/EmptyState";
import { ConfirmDeleteModal } from "../../components/ui/ConfirmDeleteModal";
import { PaginationBar } from "../../components/ui/PaginationBar";
import { PaginatedPageLayout } from "../../components/layout/PaginatedPageLayout";
import { FadeIn } from "../../components/motion/FadeIn";
import {
  StaggerContainer,
  StaggerItem,
} from "../../components/motion/StaggerContainer";

const SUPPORTED_EXTENSIONS = [".docx", ".pdf", ".md", ".markdown"];
const SUPPORTED_LABEL = SUPPORTED_EXTENSIONS.join(" / ");
const MAX_FILE_SIZE_MB = 10;

const fileIconByExtension = (filename: string) => {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".pdf")) return "📄";
  if (lower.endsWith(".docx")) return "📝";
  return "📑";
};

const DEFAULT_PAGE_SIZE = 20;

export const AdminMusicKnowledgePage = () => {
  const [sources, setSources] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [loading, setLoading] = useState(false);

  // 上传
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 删除
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 列表加载
  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const result = await musicKnowledgeApi.listDocuments({
        limit: pageSize,
        offset: page * pageSize,
      });
      setSources(result.items);
      setTotal(result.total);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "加载文档列表失败"));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const totalPages = Math.ceil(total / pageSize);

  // ---- 上传逻辑 ----
  const doUpload = async (file: File) => {
    const ext = file.name.toLowerCase();
    const isSupported = SUPPORTED_EXTENSIONS.some((e) => ext.endsWith(e));
    if (!isSupported) {
      toast.error(`不支持的文件类型，仅支持 ${SUPPORTED_LABEL}`);
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      toast.error(`文件大小超过 ${MAX_FILE_SIZE_MB} MB 限制`);
      return;
    }

    setUploading(true);
    try {
      const result = await musicKnowledgeApi.uploadDocument(file);
      toast.success(`「${result.source}」已入库（${result.chunk_count} 个片段）`);
      // 回到第一页以便看到新上传的文档
      if (page !== 0) setPage(0);
      else loadDocuments();
    } catch (err) {
      toast.error(getApiErrorMessage(err, "文档上传失败"));
    } finally {
      setUploading(false);
      // 清空 input，保证用户再次选择同名文件时仍能触发 onChange
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) doUpload(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) doUpload(file);
  };

  // ---- 删除逻辑 ----
  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      const result = await musicKnowledgeApi.deleteDocument(deleteTarget);
      toast.success(`已删除（${result.deleted_chunks} 个片段）`);
      setDeleteTarget(null);
      // 如果当前页最后一项被删除且不是第一页，回到上一页
      if (sources.length === 1 && page > 0) {
        setPage(page - 1);
      } else {
        loadDocuments();
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err, "删除文档失败"));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <PaginatedPageLayout
        header={
          <>
            <FadeIn>
              <div className="admin-page-header">
                <h1 className="page-title">音乐知识库</h1>
              </div>
            </FadeIn>

            {/* 上传区域 */}
            <FadeIn delay={0.08}>
              <div
                className={`import-image-preview-zone ${
                  dragOver ? "drag-over" : ""
                }`}
                style={{
                  minHeight: 120,
                  marginBottom: 20,
                  borderStyle: dragOver ? "solid" : "dashed",
                  borderColor: dragOver
                    ? "var(--color-ink)"
                    : "var(--color-border)",
                  opacity: uploading ? 0.6 : 1,
                  cursor: uploading ? "not-allowed" : "pointer",
                  transition: "border-color 0.2s, opacity 0.2s",
                }}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => {
                  if (!uploading) fileInputRef.current?.click();
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    if (!uploading) fileInputRef.current?.click();
                  }
                }}
                aria-disabled={uploading}
              >
                <div className="preview-placeholder" style={{ gap: 10 }}>
                  {uploading ? (
                    <Loader2
                      size={28}
                      style={{
                        color: "var(--color-muted)",
                        animation: "spin 1s linear infinite",
                      }}
                    />
                  ) : (
                    <Upload
                      size={28}
                      style={{ color: "var(--color-muted)" }}
                    />
                  )}
                  <span
                    className="placeholder-label"
                    style={{ fontWeight: 600, fontSize: 14, color: "var(--color-ink)" }}
                  >
                    {uploading ? "正在入库..." : "上传音乐知识文档"}
                  </span>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--color-muted)",
                      textAlign: "center",
                    }}
                  >
                    支持 {SUPPORTED_LABEL} · 最大 {MAX_FILE_SIZE_MB} MB · 同名文档会覆盖旧数据
                  </span>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={SUPPORTED_EXTENSIONS.join(",")}
                  onChange={handleFileChange}
                  style={{ display: "none" }}
                  disabled={uploading}
                />
              </div>
            </FadeIn>
          </>
        }
        footer={
          sources.length > 0 && (totalPages > 1 || total > 0) ? (
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
        {loading ? (
          <FadeIn delay={0.1}>
            <div
              style={{
                textAlign: "center",
                padding: "48px 0",
                color: "var(--color-muted)",
              }}
            >
              加载中...
            </div>
          </FadeIn>
        ) : sources.length > 0 ? (
          <FadeIn delay={0.1}>
            <div className="admin-table-container">
              <div
                className="admin-table-header"
                style={{ gridTemplateColumns: "48px 1fr 120px" }}
              >
                <span />
                <span>文档名称</span>
                <span>操作</span>
              </div>
              <StaggerContainer staggerDelay={0.03}>
                {sources.map((source) => (
                  <StaggerItem key={source}>
                    <motion.div
                      className="admin-table-row"
                      style={{
                        gridTemplateColumns: "48px 1fr 120px",
                        alignItems: "center",
                      }}
                      whileHover={{
                        backgroundColor: "var(--color-surface-soft)",
                      }}
                    >
                      <span style={{ fontSize: 20, textAlign: "center" }}>
                        {fileIconByExtension(source)}
                      </span>
                      <span
                        style={{
                          fontSize: 13,
                          fontWeight: 500,
                          color: "var(--color-ink)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={source}
                      >
                        {source}
                      </span>
                      <div
                        style={{
                          display: "flex",
                          gap: 6,
                          alignItems: "center",
                        }}
                      >
                        <motion.button
                          className="danger-button"
                          onClick={() => setDeleteTarget(source)}
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                          type="button"
                          title="删除文档"
                          style={{ padding: "4px 10px", minHeight: 30 }}
                        >
                          <Trash2 size={13} />
                          删除
                        </motion.button>
                      </div>
                    </motion.div>
                  </StaggerItem>
                ))}
              </StaggerContainer>
            </div>
          </FadeIn>
        ) : (
          <FadeIn delay={0.1}>
            <EmptyState
              icon={BookOpen}
              title="暂无知识库文档"
              description={`上传 ${SUPPORTED_LABEL} 格式的文档，解析后将自动切分为文本片段并写入向量库，供 AI 对话检索使用。`}
            />
          </FadeIn>
        )}
      </PaginatedPageLayout>

      <ConfirmDeleteModal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => void handleDelete()}
        loading={deleting}
        itemType="知识库文档"
        itemName={deleteTarget ?? ""}
        description="其全部向量片段将被移除，AI 将无法再检索到该文档内容。"
      />
    </>
  );
};
